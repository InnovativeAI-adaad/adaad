from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Set

from runtime.governance.canon_law import CanonLawError, emit_violation_event, load_canon_law, one_way_escalation
from runtime.governance.deterministic_filesystem import read_file_deterministic
from runtime.governance.foundation.clock import utc_now_iso
from security import cryovant

FORBIDDEN_TOKENS: Set[str] = {"os.system(", "subprocess.Popen", "eval(", "exec(", "socket."}
BANNED_IMPORTS: Set[str] = {"subprocess", "socket"}
DYNAMIC_EXEC_PRIMITIVES: Set[str] = {"eval", "exec", "compile", "__import__"}
MODULE_RUNTIME_RISKS: Set[str] = {"os", "subprocess", "socket"}
SUSPICIOUS_ATTR_INVOCATIONS: Set[str] = {"system", "popen", "popen2", "spawn", "execve"}


def _imports_in_tree(tree: ast.AST) -> Set[str]:
    found: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module.split(".")[0])
    return found


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _attribute_path(node: ast.AST) -> str | None:
    parts: list[str] = []
    current: ast.AST | None = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _ast_forbidden_patterns(tree: ast.AST) -> tuple[bool, list[str]]:
    module_aliases: dict[str, str] = {}
    symbol_aliases: dict[str, str] = {}
    reasons: list[str] = []
    dynamic_aliases: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                bound_name = alias.asname or top_level
                module_aliases[bound_name] = top_level
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level = node.module.split(".")[0]
            for alias in node.names:
                bound_name = alias.asname or alias.name
                symbol_aliases[bound_name] = f"{top_level}.{alias.name}"
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Name) and call.func.id == "getattr":
                if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
                    if call.args[1].value in DYNAMIC_EXEC_PRIMITIVES:
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                dynamic_aliases.add(target.id)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            callee = node.func.id
            if callee in DYNAMIC_EXEC_PRIMITIVES:
                reasons.append(f"dynamic_primitive:{callee}")
            mapped_symbol = symbol_aliases.get(callee)
            if callee in dynamic_aliases:
                reasons.append(f"dynamic_primitive_alias:{callee}")
            if mapped_symbol and mapped_symbol.split(".")[0] in MODULE_RUNTIME_RISKS:
                reasons.append(f"module_runtime_risk:{mapped_symbol}")
            continue

        attr_path = _attribute_path(node.func)
        if attr_path:
            parts = attr_path.split(".")
            root = parts[0]
            if root in module_aliases:
                mapped_root = module_aliases[root]
                mapped_path = ".".join([mapped_root, *parts[1:]])
                if mapped_root in MODULE_RUNTIME_RISKS:
                    reasons.append(f"module_runtime_risk:{mapped_path}")
                if mapped_root in MODULE_RUNTIME_RISKS and parts[-1] in SUSPICIOUS_ATTR_INVOCATIONS:
                    reasons.append(f"suspicious_attribute_invocation:{mapped_path}")
            if parts[-1] in DYNAMIC_EXEC_PRIMITIVES:
                reasons.append(f"attribute_dynamic_primitive:{attr_path}")

        if isinstance(node.func, ast.Call) and isinstance(node.func.func, ast.Name) and node.func.func.id == "getattr":
            getter_args = node.func.args
            if len(getter_args) >= 2 and isinstance(getter_args[1], ast.Constant) and isinstance(getter_args[1].value, str):
                attr_name = getter_args[1].value
                if attr_name in DYNAMIC_EXEC_PRIMITIVES:
                    reasons.append(f"getattr_dynamic_primitive:{attr_name}")

    return (len(reasons) == 0, sorted(set(reasons)))


@dataclass
class GateCertifier:
    forbidden_tokens: Set[str] = field(default_factory=lambda: set(FORBIDDEN_TOKENS))
    banned_imports: Set[str] = field(default_factory=lambda: set(BANNED_IMPORTS))
    clock_now_iso: Callable[[], str] = utc_now_iso

    def certify(self, file_path: Path, metadata: Dict[str, str] | None = None) -> Dict[str, object]:
        metadata = dict(metadata or {})
        escalation = "advisory"
        try:
            clauses = load_canon_law()
        except CanonLawError as exc:
            return self._result(False, metadata, error=f"canon_law_error:{exc}", file=str(file_path), escalation="critical", mutation_blocked=True, fail_closed=True, event=[])
        mutation_blocked = False
        fail_closed = False

        def _record(clause_id: str, reason: str, *, context: Dict[str, object] | None = None) -> dict[str, object]:
            nonlocal escalation, mutation_blocked, fail_closed
            clause = clauses[clause_id]
            entry = emit_violation_event(component="gate_certifier", clause=clause, reason=reason, context=context)
            escalation = one_way_escalation(escalation, clause.escalation)
            mutation_blocked = mutation_blocked or clause.mutation_block
            fail_closed = fail_closed or clause.fail_closed
            return {"ledger_hash": entry.get("hash", "")}

        if not file_path.exists() or file_path.is_dir():
            evt = _record("III.gate_file_must_exist", "missing_file", context={"file": str(file_path)})
            return self._result(
                False,
                metadata,
                error="missing_file",
                file=str(file_path),
                escalation=escalation,
                mutation_blocked=mutation_blocked,
                fail_closed=fail_closed,
                event=evt,
            )
        content = read_file_deterministic(file_path)

        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            evt = _record("IV.gate_forbidden_code_block", "syntax_error", context={"error": str(exc), "file": str(file_path)})
            return self._result(
                False,
                metadata,
                error=f"syntax_error:{exc}",
                file=str(file_path),
                escalation=escalation,
                mutation_blocked=mutation_blocked,
                fail_closed=fail_closed,
                event=evt,
            )
        except CanonLawError as exc:
            evt = _record("VIII.undefined_state_fail_closed", "undefined_state", context={"error": str(exc), "file": str(file_path)})
            return self._result(
                False,
                metadata,
                error=f"undefined_state:{exc}",
                file=str(file_path),
                escalation=escalation,
                mutation_blocked=mutation_blocked,
                fail_closed=fail_closed,
                event=evt,
            )

        found_imports = _imports_in_tree(tree)
        import_ok = not any(bad in found_imports for bad in self.banned_imports)
        token_ok = not any(tok in content for tok in self.forbidden_tokens)
        ast_ok, ast_violations = _ast_forbidden_patterns(tree)

        token = (metadata.get("cryovant_token") or "").strip()
        auth_ok = False
        if token:
            try:
                auth_ok = bool(cryovant.verify_session(token))
            except Exception:
                auth_ok = False

        passed = import_ok and ast_ok and auth_ok
        violation_events: list[dict[str, object]] = []
        if not import_ok or not ast_ok:
            violation_events.append(_record("IV.gate_forbidden_code_block", "forbidden_code_or_import"))
        if not auth_ok:
            violation_events.append(_record("V.gate_authentication_required", "auth_failed"))
        metadata.pop("cryovant_token", None)
        return self._result(
            passed,
            metadata,
            file=str(file_path),
            hash=_sha256_text(content),
            checks={
                "imports": sorted(found_imports),
                "import_ok": import_ok,
                "token_ok": token_ok,
                "ast_ok": ast_ok,
                "ast_violations": ast_violations,
                "auth_ok": auth_ok,
            },
            escalation=escalation,
            mutation_blocked=mutation_blocked,
            fail_closed=fail_closed,
            event=violation_events,
        )

    def _result(self, passed: bool, metadata: Dict[str, str], **kwargs: object) -> Dict[str, object]:
        return {
            "status": "CERTIFIED" if passed else "REJECTED",
            "passed": passed,
            "generated_at": self.clock_now_iso(),
            "metadata": metadata,
            **kwargs,
        }


__all__ = ["GateCertifier"]

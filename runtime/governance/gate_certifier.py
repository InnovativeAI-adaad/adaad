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


def _ast_forbidden_patterns(tree: ast.AST) -> tuple[bool, list[str], list[dict[str, object]]]:
    reasons: set[str] = set()
    reason_lines: dict[str, int] = {}

    def _add_reason(reason: str, line: int | None) -> None:
        reasons.add(reason)
        if line is not None and reason not in reason_lines:
            reason_lines[reason] = line

    class _SecurityVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.aliases: dict[str, str] = {}

        def _resolve_expr(self, node: ast.AST) -> str | None:
            if isinstance(node, ast.Name):
                return self.aliases.get(node.id, node.id)
            if isinstance(node, ast.Attribute):
                base = self._resolve_expr(node.value)
                return f"{base}.{node.attr}" if base else None
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "getattr":
                    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                        base = self._resolve_expr(node.args[0])
                        return f"{base}.{node.args[1].value}" if base else node.args[1].value
                if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        return node.args[0].value.split(".")[0]
            return _attribute_path(node)

        def _record_call_path(self, path: str, call_node: ast.Call) -> None:
            parts = path.split(".")
            root = parts[0]
            leaf = parts[-1]

            if isinstance(call_node.func, ast.Name) and call_node.func.id in DYNAMIC_EXEC_PRIMITIVES:
                _add_reason(f"dynamic_primitive:{call_node.func.id}", getattr(call_node, "lineno", None))

            if isinstance(call_node.func, ast.Name) and call_node.func.id in self.aliases:
                resolved = self.aliases[call_node.func.id]
                if resolved.split(".")[-1] in DYNAMIC_EXEC_PRIMITIVES:
                    _add_reason(f"dynamic_primitive_alias:{call_node.func.id}", getattr(call_node, "lineno", None))

            if leaf in DYNAMIC_EXEC_PRIMITIVES:
                _add_reason(f"attribute_dynamic_primitive:{path}", getattr(call_node, "lineno", None))

            if root in MODULE_RUNTIME_RISKS:
                _add_reason(f"module_runtime_risk:{path}", getattr(call_node, "lineno", None))
                if leaf in SUSPICIOUS_ATTR_INVOCATIONS:
                    _add_reason(f"suspicious_attribute_invocation:{path}", getattr(call_node, "lineno", None))

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                self.aliases[alias.asname or top_level] = top_level

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if not node.module:
                return
            top_level = node.module.split(".")[0]
            for alias in node.names:
                bound_name = alias.asname or alias.name
                self.aliases[bound_name] = f"{top_level}.{alias.name}"

        def visit_Assign(self, node: ast.Assign) -> None:
            resolved = self._resolve_expr(node.value)
            if resolved:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.aliases[target.id] = resolved
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            path = self._resolve_expr(node.func)
            if path:
                self._record_call_path(path, node)
            self.generic_visit(node)

    _SecurityVisitor().visit(tree)

    sorted_reasons = sorted(reasons)
    semantic_violations: list[dict[str, object]] = []
    for detail in sorted_reasons:
        kind, _, remainder = detail.partition(":")
        semantic_violations.append(
            {
                "kind": kind,
                "detail": remainder,
                "line": reason_lines.get(detail),
            }
        )

    return (len(reasons) == 0, sorted_reasons, semantic_violations)


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
        ast_ok, ast_violations, semantic_violations = _ast_forbidden_patterns(tree)

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
                "semantic_violations": semantic_violations,
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

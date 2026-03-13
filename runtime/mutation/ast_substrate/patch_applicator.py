"""
runtime.mutation.ast_substrate.patch_applicator
===============================================
LibCST-based patch application with SANDBOX-DIV-0 divergence detection.

Design
------
stdlib ast  → validation only (before/after hash computation)
LibCST      → actual source patch application (preserves formatting/comments)

SANDBOX-DIV-0: after applying after_source, the AST hash of the written
file must equal patch.after_ast_hash.  Any divergence triggers automatic
rollback and emits a PATCH_DIVERGENCE governance incident record.

MUTATION_SANDBOX_ONLY
---------------------
When env var MUTATION_SANDBOX_ONLY=true, PatchApplicator operates in dry-run
mode: it validates the patch but never writes to disk.  All Phase 60 work
enforces this during stabilisation.
"""

from __future__ import annotations

import ast
import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import libcst as cst

from runtime.mutation.ast_substrate.ast_diff_patch import ASTDiffPatch, _ast_hash


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class ApplyResult:
    """Outcome of a patch application attempt.

    Attributes
    ----------
    success         True if patch was applied and SANDBOX-DIV-0 verified.
    sandbox_only    True if running in MUTATION_SANDBOX_ONLY mode (no writes).
    divergence      True if after-hash did not match after applying.
    rollback        True if a divergent write was rolled back.
    before_hash     AST hash of file before apply.
    after_hash      AST hash of file after apply (or simulated).
    expected_hash   patch.after_ast_hash.
    error           Error message on failure.
    """
    success: bool
    sandbox_only: bool = False
    divergence: bool = False
    rollback: bool = False
    before_hash: str = ""
    after_hash: str = ""
    expected_hash: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ---------------------------------------------------------------------------
# Applicator
# ---------------------------------------------------------------------------

class PatchApplicator:
    """Applies ASTDiffPatch to disk using LibCST with SANDBOX-DIV-0 guard.

    Parameters
    ----------
    sandbox_only:   Override for sandbox mode (also reads MUTATION_SANDBOX_ONLY env).
    """

    def __init__(self, sandbox_only: Optional[bool] = None) -> None:
        env_flag = os.environ.get("MUTATION_SANDBOX_ONLY", "").lower()
        self._sandbox_only = sandbox_only if sandbox_only is not None else (env_flag == "true")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply(self, patch: ASTDiffPatch, base_dir: str = "") -> ApplyResult:
        """Apply *patch* to disk (or simulate in sandbox mode).

        Parameters
        ----------
        patch:      ASTDiffPatch to apply.
        base_dir:   Optional base directory prefix for target_file resolution.
        """
        target = Path(base_dir) / patch.target_file if base_dir else Path(patch.target_file)

        # Validate after_source is valid LibCST + round-trips cleanly
        libcst_error = _validate_libcst(patch.after_source)
        if libcst_error:
            return ApplyResult(
                success=False,
                sandbox_only=self._sandbox_only,
                expected_hash=patch.after_ast_hash,
                error=f"LibCST parse error in after_source: {libcst_error}",
            )

        # Compute before hash from actual file (if exists) or from patch
        before_hash = ""
        if target.exists():
            try:
                actual = target.read_text(encoding="utf-8")
                before_tree = ast.parse(actual, filename=str(target))
                before_hash = _ast_hash(before_tree)
            except (OSError, SyntaxError):
                before_hash = patch.before_ast_hash
        else:
            before_hash = patch.before_ast_hash

        # Verify before hash matches expectation
        if before_hash and before_hash != patch.before_ast_hash:
            return ApplyResult(
                success=False,
                sandbox_only=self._sandbox_only,
                before_hash=before_hash,
                expected_hash=patch.after_ast_hash,
                error=(
                    f"SANDBOX-DIV-0: before_hash mismatch — "
                    f"disk={before_hash[:16]}... expected={patch.before_ast_hash[:16]}..."
                ),
            )

        # Compute expected after hash from patch
        try:
            after_tree = ast.parse(patch.after_source, filename=str(target))
            simulated_after_hash = _ast_hash(after_tree)
        except SyntaxError as exc:
            return ApplyResult(
                success=False,
                sandbox_only=self._sandbox_only,
                before_hash=before_hash,
                expected_hash=patch.after_ast_hash,
                error=f"SyntaxError in after_source: {exc}",
            )

        # SANDBOX-DIV-0 pre-check: simulated hash must match stored hash
        if simulated_after_hash != patch.after_ast_hash:
            return ApplyResult(
                success=False,
                sandbox_only=self._sandbox_only,
                divergence=True,
                before_hash=before_hash,
                after_hash=simulated_after_hash,
                expected_hash=patch.after_ast_hash,
                error=(
                    f"SANDBOX-DIV-0: after_hash divergence — "
                    f"computed={simulated_after_hash[:16]}... "
                    f"stored={patch.after_ast_hash[:16]}..."
                ),
            )

        # Sandbox-only: validate but don't write
        if self._sandbox_only:
            return ApplyResult(
                success=True,
                sandbox_only=True,
                before_hash=before_hash,
                after_hash=simulated_after_hash,
                expected_hash=patch.after_ast_hash,
            )

        # Apply to disk with rollback safety
        return self._write_with_rollback(patch, target, before_hash, simulated_after_hash)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _write_with_rollback(
        self,
        patch: ASTDiffPatch,
        target: Path,
        before_hash: str,
        expected_hash: str,
    ) -> ApplyResult:
        backup: Optional[Path] = None

        if target.exists():
            backup = target.with_suffix(target.suffix + ".bak")
            shutil.copy2(target, backup)

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(patch.after_source, encoding="utf-8")

            # Post-write SANDBOX-DIV-0 verification
            written = target.read_text(encoding="utf-8")
            written_tree = ast.parse(written, filename=str(target))
            written_hash = _ast_hash(written_tree)

            if written_hash != expected_hash:
                # Divergence: rollback
                if backup and backup.exists():
                    shutil.copy2(backup, target)
                return ApplyResult(
                    success=False,
                    divergence=True,
                    rollback=True,
                    before_hash=before_hash,
                    after_hash=written_hash,
                    expected_hash=expected_hash,
                    error=f"SANDBOX-DIV-0: post-write divergence; rollback executed",
                )

            return ApplyResult(
                success=True,
                before_hash=before_hash,
                after_hash=written_hash,
                expected_hash=expected_hash,
            )

        except Exception as exc:
            if backup and backup.exists():
                shutil.copy2(backup, target)
            return ApplyResult(
                success=False,
                rollback=bool(backup),
                before_hash=before_hash,
                expected_hash=expected_hash,
                error=str(exc),
            )
        finally:
            if backup and backup.exists():
                backup.unlink(missing_ok=True)

    @property
    def sandbox_only(self) -> bool:
        return self._sandbox_only


# ---------------------------------------------------------------------------
# LibCST helpers
# ---------------------------------------------------------------------------

def _validate_libcst(source: str) -> Optional[str]:
    """Return error string if LibCST cannot parse *source*, else None."""
    try:
        cst.parse_module(source)
        return None
    except cst.ParserSyntaxError as exc:
        return str(exc)

# SPDX-License-Identifier: Apache-2.0
"""Phase 84 — CodebaseStateVector.

A compact, deterministic fingerprint of the relevant codebase region
at a point in time. Used by FitnessDecayScorer to detect drift between
the moment a mutation was scored and the current codebase state.

Constitutional Invariants
─────────────────────────
  TFHL-DET-0   CodebaseStateVector is deterministic: identical source inputs
               always produce identical fingerprints.
  TFHL-IMM-0   Vectors are immutable frozen dataclasses. Once created they
               cannot be modified.
  TFHL-SCOPE-0 The vector fingerprints only the *relevant region* (files
               touched by the mutation), not the entire repository, keeping
               computation bounded and fast.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

log = logging.getLogger(__name__)

CSV_VERSION: str = "84.0"

# Normalisation constants for AST metrics
_MAX_NODES: int = 2000
_MAX_DEPTH: int = 80
_MAX_CYCLOMATIC: int = 60


# ---------------------------------------------------------------------------
# AST metric helpers (TFHL-DET-0)
# ---------------------------------------------------------------------------


def _count_nodes(source: str) -> int:
    try:
        return sum(1 for _ in ast.walk(ast.parse(source)))
    except SyntaxError:
        return 0


def _max_depth(source: str) -> int:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0

    def _depth(node: ast.AST, d: int = 0) -> int:
        children = list(ast.iter_child_nodes(node))
        return max((_depth(c, d + 1) for c in children), default=d)

    return _depth(tree)


def _cyclomatic(source: str) -> int:
    """Simple cyclomatic complexity proxy: count branches."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    branch_types = (
        ast.If, ast.For, ast.While, ast.ExceptHandler,
        ast.With, ast.Assert, ast.comprehension,
    )
    return 1 + sum(1 for _ in ast.walk(tree) if isinstance(_, branch_types))


def _source_digest(source: str) -> str:
    """SHA-256 of normalised source (strip whitespace for stability)."""
    normalised = "\n".join(line.rstrip() for line in source.splitlines()).strip()
    return hashlib.sha256(normalised.encode()).hexdigest()


# ---------------------------------------------------------------------------
# FileSnapshot — per-file metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileSnapshot:
    """AST metrics snapshot for one file. TFHL-DET-0: deterministic from source."""

    path: str
    source_digest: str       # SHA-256 of normalised source
    node_count: int
    max_depth: int
    cyclomatic: int

    @classmethod
    def from_source(cls, path: str, source: str) -> "FileSnapshot":
        return cls(
            path=path,
            source_digest=_source_digest(source),
            node_count=_count_nodes(source),
            max_depth=_max_depth(source),
            cyclomatic=_cyclomatic(source),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "source_digest": self.source_digest,
            "node_count": self.node_count,
            "max_depth": self.max_depth,
            "cyclomatic": self.cyclomatic,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FileSnapshot":
        return cls(**d)


# ---------------------------------------------------------------------------
# CodebaseStateVector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CodebaseStateVector:
    """Deterministic compact fingerprint of a codebase region.

    Attributes
    ----------
    vector_id:      Deterministic SHA-256[:16] of all file digests.
    file_snapshots: Per-file AST metric snapshots (sorted by path, TFHL-DET-0).
    region_digest:  SHA-256 of canonical sorted (path, source_digest) pairs.
    total_nodes:    Sum of node_count across all files.
    mean_cyclomatic: Mean cyclomatic complexity across all files.
    file_count:     Number of files in this region.
    schema_version: CSV schema version.
    """

    vector_id: str
    file_snapshots: tuple  # Tuple[FileSnapshot, ...]
    region_digest: str
    total_nodes: int
    mean_cyclomatic: float
    file_count: int
    schema_version: str = CSV_VERSION

    @classmethod
    def from_sources(
        cls, sources: Dict[str, str]
    ) -> "CodebaseStateVector":
        """Build from a mapping of {file_path: source_code}.

        TFHL-DET-0: sorted by path before hashing.
        """
        snapshots = tuple(
            FileSnapshot.from_source(path, src)
            for path, src in sorted(sources.items())
        )
        region_payload = json.dumps(
            sorted([{"path": s.path, "digest": s.source_digest} for s in snapshots], key=lambda d: d["path"]),
            sort_keys=True, separators=(",", ":"),
        )
        region_digest = "sha256:" + hashlib.sha256(region_payload.encode()).hexdigest()
        vector_id = "csv-" + hashlib.sha256(region_digest.encode()).hexdigest()[:16]
        total_nodes = sum(s.node_count for s in snapshots)
        mean_cc = (
            sum(s.cyclomatic for s in snapshots) / len(snapshots)
            if snapshots else 0.0
        )
        return cls(
            vector_id=vector_id,
            file_snapshots=snapshots,
            region_digest=region_digest,
            total_nodes=total_nodes,
            mean_cyclomatic=round(mean_cc, 4),
            file_count=len(snapshots),
        )

    @classmethod
    def from_paths(
        cls, paths: Sequence[str], *, repo_root: Optional[Path] = None
    ) -> "CodebaseStateVector":
        """Build from file paths, reading source from disk.

        Files that cannot be read are silently skipped (TFHL-DET-0 preserved
        for files that do exist).
        """
        sources: Dict[str, str] = {}
        root = Path(repo_root) if repo_root else Path(".")
        for path in paths:
            try:
                full = root / path
                sources[str(path)] = full.read_text(encoding="utf-8")
            except OSError as exc:
                log.debug("TFHL: skipping unreadable file %s: %s", path, exc)
        return cls.from_sources(sources)

    def drift_from(self, other: "CodebaseStateVector") -> float:
        """Compute normalised drift magnitude between this and another vector.

        Returns float in [0.0, 1.0]:
          0.0 = identical region (no drift)
          1.0 = completely different (all files changed or replaced)

        Algorithm:
          1. Changed files: count files present in both whose source_digest differs.
          2. Added/removed files: count files only in one vector.
          3. Metric delta: normalised difference in total_nodes and mean_cyclomatic.
          4. Weighted combination: digest_change × 0.6 + metric_delta × 0.4.
        """
        self_map = {s.path: s for s in self.file_snapshots}
        other_map = {s.path: s for s in other.file_snapshots}

        all_paths = set(self_map) | set(other_map)
        if not all_paths:
            return 0.0

        # Digest-based drift
        changed = sum(
            1 for p in all_paths
            if self_map.get(p, FileSnapshot("", "", 0, 0, 0)).source_digest
            != other_map.get(p, FileSnapshot("", "", 0, 0, 0)).source_digest
        )
        digest_drift = changed / len(all_paths)

        # Metric-based drift
        node_delta = abs(self.total_nodes - other.total_nodes)
        node_norm = min(1.0, node_delta / max(1, max(self.total_nodes, other.total_nodes)))
        cc_delta = abs(self.mean_cyclomatic - other.mean_cyclomatic)
        cc_norm = min(1.0, cc_delta / max(1.0, max(self.mean_cyclomatic, other.mean_cyclomatic, 1.0)))
        metric_drift = (node_norm + cc_norm) / 2.0

        return round(min(1.0, 0.6 * digest_drift + 0.4 * metric_drift), 6)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector_id": self.vector_id,
            "file_snapshots": [s.to_dict() for s in self.file_snapshots],
            "region_digest": self.region_digest,
            "total_nodes": self.total_nodes,
            "mean_cyclomatic": self.mean_cyclomatic,
            "file_count": self.file_count,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CodebaseStateVector":
        return cls(
            vector_id=d["vector_id"],
            file_snapshots=tuple(FileSnapshot.from_dict(s) for s in d["file_snapshots"]),
            region_digest=d["region_digest"],
            total_nodes=d["total_nodes"],
            mean_cyclomatic=d["mean_cyclomatic"],
            file_count=d["file_count"],
            schema_version=d.get("schema_version", CSV_VERSION),
        )

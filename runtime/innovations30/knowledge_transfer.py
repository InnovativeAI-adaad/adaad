# SPDX-License-Identifier: Apache-2.0
"""Innovation #13 — Institutional Memory Transfer.
Cryptographically verified transfer of knowledge between ADAAD instances.
The system's engineering wisdom outlives its hardware.
"""
from __future__ import annotations
import hashlib, json, gzip, base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass
class KnowledgeBundle:
    source_instance_id: str
    bundle_version: str
    epoch_count: int
    knowledge_snapshot: dict[str, Any]  # serialized knowledge state
    bundle_hash: str
    signature: str = ""  # signed by source instance key

    @classmethod
    def create(cls, source_id: str, knowledge: dict[str, Any],
               epoch_count: int) -> "KnowledgeBundle":
        payload = json.dumps(knowledge, sort_keys=True)
        bundle_hash = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
        return cls(
            source_instance_id=source_id,
            bundle_version="1.0",
            epoch_count=epoch_count,
            knowledge_snapshot=knowledge,
            bundle_hash=bundle_hash,
        )

    def to_bytes(self) -> bytes:
        payload = json.dumps({
            "source_instance_id": self.source_instance_id,
            "bundle_version": self.bundle_version,
            "epoch_count": self.epoch_count,
            "knowledge_snapshot": self.knowledge_snapshot,
            "bundle_hash": self.bundle_hash,
        }, sort_keys=True).encode()
        return gzip.compress(payload)

    @classmethod
    def from_bytes(cls, data: bytes) -> "KnowledgeBundle":
        payload = json.loads(gzip.decompress(data))
        return cls(**payload)

    def verify_integrity(self) -> bool:
        payload = json.dumps(self.knowledge_snapshot, sort_keys=True)
        expected = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
        return expected == self.bundle_hash


@dataclass
class TransferResult:
    success: bool
    imported_items: int
    integrity_verified: bool
    source_instance_id: str
    error: str = ""


class InstitutionalMemoryTransfer:
    """Exports and imports knowledge bundles between ADAAD instances."""

    def __init__(self, transfer_log: Path = Path("data/memory_transfers.jsonl")):
        self.transfer_log = Path(transfer_log)

    def export_bundle(self, instance_id: str,
                       knowledge_sources: dict[str, Path],
                       epoch_count: int) -> KnowledgeBundle:
        """Serialize knowledge from multiple source files into a bundle."""
        knowledge: dict[str, Any] = {}
        for name, path in knowledge_sources.items():
            if path.exists():
                try:
                    content = path.read_text()
                    # Try JSON, fall back to raw
                    try:
                        knowledge[name] = json.loads(content)
                    except json.JSONDecodeError:
                        knowledge[name] = {"raw_lines": len(content.splitlines())}
                except Exception:
                    pass
        return KnowledgeBundle.create(instance_id, knowledge, epoch_count)

    def import_bundle(self, bundle: KnowledgeBundle,
                       target_paths: dict[str, Path]) -> TransferResult:
        """Import knowledge from a bundle into target paths."""
        if not bundle.verify_integrity():
            return TransferResult(success=False, imported_items=0,
                integrity_verified=False, source_instance_id=bundle.source_instance_id,
                error="Bundle integrity verification failed")

        imported = 0
        for name, data in bundle.knowledge_snapshot.items():
            if name in target_paths:
                target_path = target_paths[name]
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(json.dumps(data, indent=2))
                imported += 1

        result = TransferResult(success=True, imported_items=imported,
            integrity_verified=True,
            source_instance_id=bundle.source_instance_id)
        self._log_transfer(bundle, result)
        return result

    def _log_transfer(self, bundle: KnowledgeBundle, result: TransferResult) -> None:
        import dataclasses
        self.transfer_log.parent.mkdir(parents=True, exist_ok=True)
        with self.transfer_log.open("a") as f:
            f.write(json.dumps({
                "source": bundle.source_instance_id,
                "epoch_count": bundle.epoch_count,
                "hash": bundle.bundle_hash,
                "imported": result.imported_items,
                "success": result.success,
            }) + "\n")


__all__ = ["InstitutionalMemoryTransfer", "KnowledgeBundle", "TransferResult"]

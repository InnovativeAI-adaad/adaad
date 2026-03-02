from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> None:
    fixture = os.environ["GENERATED_FIXTURE"]
    evidence_dir = Path(os.environ["GENERATED_EVIDENCE_DIR"])
    reports_dir = Path(os.environ["GENERATED_REPORTS_DIR"])

    lanes = {
        "pytest": os.environ.get("LANE_PYTEST", "unknown"),
        "mypy": os.environ.get("LANE_MYPY", "unknown"),
        "bandit": os.environ.get("LANE_BANDIT", "unknown"),
        "sandbox": os.environ.get("LANE_SANDBOX", "unknown"),
    }
    pass_count = sum(1 for v in lanes.values() if v == "success")
    fail_count = sum(1 for v in lanes.values() if v != "success")

    hashes: dict[str, str] = {}
    for root in (evidence_dir, reports_dir):
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            hashes[str(path.relative_to(root))] = sha256_file(path)

    payload = {
        "fixture": fixture,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "lanes": lanes,
        "counts": {"pass": pass_count, "fail": fail_count},
        "hashes": hashes,
    }
    output = reports_dir / "metadata-summary.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
ADAAD_ROOT="${ADAAD_ROOT:-${DEFAULT_ROOT}}"

cd "${ADAAD_ROOT}"
PYTHONPATH=. /usr/bin/python3 scripts/verify_critical_artifacts.py


#!/usr/bin/env bash
# =============================================================
# ADAAD Codex Maintenance Script
# Runs in cached containers BEFORE each task.
# Invariants: [INV-PATH] [INV-RUNTIME] [INV-AUDIT]
# Fail-closed: abort if workspace or runtime has drifted.
# =============================================================
set -euo pipefail

WORKSPACE_ROOT="/workspace"
REPO_NAME="adaad"
REPO_DIR="${WORKSPACE_ROOT}/${REPO_NAME}"

# ── [INV-PATH] ─────────────────────────────────────────────
if [[ ! -d "${REPO_DIR}" ]]; then
  echo "[ADAAD-MAINT][FATAL][INV-PATH] Repo dir absent after cache restore: ${REPO_DIR}" >&2
  exit 1
fi
cd "${REPO_DIR}"

# ── [INV-RUNTIME] ──────────────────────────────────────────
PYTHON_BIN="${PYTHON:-python3.11}"
command -v "${PYTHON_BIN}" &>/dev/null || PYTHON_BIN="python3"

PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${PYTHON_VERSION}" != "3.11" ]]; then
  echo "[ADAAD-MAINT][FATAL][INV-RUNTIME] Runtime drift detected: expected 3.11, found ${PYTHON_VERSION}" >&2
  exit 1
fi

# ── Re-validate dep snapshot vs current pip freeze ─────────
SNAPSHOT_FILE="${REPO_DIR}/.codex/dep_snapshot.sha256"
if [[ -f "${SNAPSHOT_FILE}" ]]; then
  EXPECTED_HASH="$(awk '{print $1}' "${SNAPSHOT_FILE}")"
  CURRENT_HASH="$("${PYTHON_BIN}" -m pip freeze | sha256sum | awk '{print $1}')"
  if [[ "${EXPECTED_HASH}" != "${CURRENT_HASH}" ]]; then
    echo "[ADAAD-MAINT][WARN][INV-DEP] Dependency drift detected — reinstalling from requirements.txt"
    "${PYTHON_BIN}" -m pip install -r "${REPO_DIR}/requirements.txt" --quiet
    "${PYTHON_BIN}" -m pip freeze | sha256sum > "${SNAPSHOT_FILE}"
    echo "[ADAAD-MAINT][INFO] Snapshot refreshed."
  else
    echo "[ADAAD-MAINT][INFO] Dependency snapshot clean — no drift."
  fi
fi

# ── Pull latest & re-anchor audit manifest ─────────────────
git fetch --quiet origin 2>/dev/null || true
GIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo 'UNKNOWN')"
MAINT_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

MANIFEST="${REPO_DIR}/.codex/setup_manifest.json"
if [[ -f "${MANIFEST}" ]]; then
  # Update git_sha and timestamp in-place using Python (no jq dependency).
  "${PYTHON_BIN}" - <<PYEOF
import json, pathlib
p = pathlib.Path("${MANIFEST}")
d = json.loads(p.read_text())
d["git_sha"] = "${GIT_SHA}"
d["maintenance_timestamp_utc"] = "${MAINT_TIMESTAMP}"
d["status"] = "MAINTENANCE_VERIFIED"
p.write_text(json.dumps(d, indent=2))
PYEOF
fi

echo "[ADAAD-MAINT][INFO] Maintenance verified — git@${GIT_SHA:0:8} | ${MAINT_TIMESTAMP}"

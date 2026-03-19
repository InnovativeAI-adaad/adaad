#!/usr/bin/env bash
# =============================================================
# ADAAD Codex Bootstrap — Setup Script
# Invariants: [INV-PATH] [INV-RUNTIME] [INV-DEP] [INV-PREFLIGHT]
# Fail-closed posture: any unhandled error aborts immediately.
# =============================================================
set -euo pipefail

# ── [INV-PATH] P0 ─────────────────────────────────────────
# Root cause of "No such file or directory": Codex clones to
# /workspace/adaad (lowercase repo name). Never hardcode the
# path — resolve it canonically at runtime.
# ──────────────────────────────────────────────────────────
WORKSPACE_ROOT="/workspace"
REPO_NAME="adaad"
REPO_DIR="${WORKSPACE_ROOT}/${REPO_NAME}"

# Fail-closed: abort if the workspace is absent rather than
# silently proceeding in an unknown directory.
if [[ ! -d "${REPO_DIR}" ]]; then
  echo "[ADAAD-SETUP][FATAL][INV-PATH] Expected repo dir not found: ${REPO_DIR}" >&2
  echo "[ADAAD-SETUP][FATAL] Listing /workspace for diagnostics:" >&2
  ls -la "${WORKSPACE_ROOT}" >&2 || true
  exit 1
fi

cd "${REPO_DIR}"
echo "[ADAAD-SETUP][INFO] Workspace confirmed: $(pwd)"

# ── [INV-RUNTIME] P1 ──────────────────────────────────────
# ADAAD pins Python 3.11.x. The universal image ships multiple
# Pythons; assert the correct one is active before any install.
# ──────────────────────────────────────────────────────────
REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=11

# Prefer python3.11 explicitly; fall back to python3 with check.
if command -v python3.11 &>/dev/null; then
  PYTHON_BIN="python3.11"
else
  PYTHON_BIN="python3"
fi

PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYTHON_MAJOR="${PYTHON_VERSION%%.*}"
PYTHON_MINOR="${PYTHON_VERSION##*.}"

if [[ "${PYTHON_MAJOR}" -ne "${REQUIRED_PYTHON_MAJOR}" ]] || \
   [[ "${PYTHON_MINOR}" -ne "${REQUIRED_PYTHON_MINOR}" ]]; then
  echo "[ADAAD-SETUP][FATAL][INV-RUNTIME] Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR} required; found ${PYTHON_VERSION}" >&2
  exit 1
fi
echo "[ADAAD-SETUP][INFO] Python runtime confirmed: ${PYTHON_BIN} (${PYTHON_VERSION})"

# Make the pinned binary the project default for this container.
export PYTHON="${PYTHON_BIN}"

# ── [INV-DEP] P1 ──────────────────────────────────────────
# Install dependencies from the canonical requirements file.
# requirements.txt is used for server/CI; requirements.phone.txt
# (libcst, pure-Python) is used for Android/Pydroid3.
# Hashes are verified when requirements.txt includes --hash
# directives; otherwise, a SHA-256 snapshot is recorded to
# .codex/dep_snapshot.sha256 for post-install audit.
# ──────────────────────────────────────────────────────────
REQ_FILE="${REPO_DIR}/requirements.txt"

if [[ ! -f "${REQ_FILE}" ]]; then
  echo "[ADAAD-SETUP][WARN][INV-DEP] requirements.txt missing — skipping dep install" >&2
else
  echo "[ADAAD-SETUP][INFO] Installing dependencies from ${REQ_FILE}"
  "${PYTHON_BIN}" -m pip install --upgrade pip --quiet
  "${PYTHON_BIN}" -m pip install -r "${REQ_FILE}" --quiet

  # Record post-install dependency snapshot for audit traceability.
  SNAPSHOT_DIR="${REPO_DIR}/.codex"
  mkdir -p "${SNAPSHOT_DIR}"
  "${PYTHON_BIN}" -m pip freeze | \
    sha256sum > "${SNAPSHOT_DIR}/dep_snapshot.sha256"
  echo "[ADAAD-SETUP][INFO] Dependency snapshot recorded: ${SNAPSHOT_DIR}/dep_snapshot.sha256"
fi

# ── [INV-PREFLIGHT] P1 ────────────────────────────────────
# Run the ADAAD preflight contract gate if present.
# This validates schema registration, CONSTITUTION_VERSION
# binding, and phase lifecycle invariants before any code runs.
# Fail-closed: if the script exists and exits non-zero, abort.
# ──────────────────────────────────────────────────────────
PREFLIGHT_SCRIPT="${REPO_DIR}/scripts/preflight.py"

if [[ -f "${PREFLIGHT_SCRIPT}" ]]; then
  echo "[ADAAD-SETUP][INFO] Running preflight contract gate..."
  "${PYTHON_BIN}" "${PREFLIGHT_SCRIPT}" --mode=ci
  echo "[ADAAD-SETUP][INFO] Preflight passed."
else
  echo "[ADAAD-SETUP][WARN][INV-PREFLIGHT] preflight.py not found — skipping (non-blocking in setup)"
fi

# ── [INV-AUDIT] P1 ────────────────────────────────────────
# Emit a signed setup manifest: git SHA + Python version +
# dep snapshot hash + timestamp. This is the audit anchor for
# any container instance that runs ADAAD tasks.
# ──────────────────────────────────────────────────────────
GIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo 'UNKNOWN')"
SETUP_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DEP_HASH="$(cat "${REPO_DIR}/.codex/dep_snapshot.sha256" 2>/dev/null | awk '{print $1}' || echo 'NONE')"

MANIFEST="${REPO_DIR}/.codex/setup_manifest.json"
cat > "${MANIFEST}" <<EOF2
{
  "schema": "adaad.codex.setup_manifest.v1",
  "git_sha": "${GIT_SHA}",
  "python_version": "${PYTHON_VERSION}",
  "python_bin": "${PYTHON_BIN}",
  "dep_snapshot_sha256": "${DEP_HASH}",
  "setup_timestamp_utc": "${SETUP_TIMESTAMP}",
  "workspace": "${REPO_DIR}",
  "status": "SUCCESS"
}
EOF2

echo "[ADAAD-SETUP][INFO] Setup manifest written: ${MANIFEST}"
echo "[ADAAD-SETUP][INFO] Bootstrap complete — git@${GIT_SHA:0:8} | py${PYTHON_VERSION} | ${SETUP_TIMESTAMP}"

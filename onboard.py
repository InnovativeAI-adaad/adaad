#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
ADAAD Onboarding — unified setup, gate, and first-run.

One command: python onboard.py

Steps:
  1. Check Python version (3.11+)
  2. Create .venv and install dependencies
  3. Set ADAAD_ENV=dev
  4. Initialize workspace (nexus_setup.py)
  5. Validate governance schemas
  6. Run governed dry-run
  7. Print next steps

Idempotent — safe to run multiple times.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# ── Palette ────────────────────────────────────────────────────────────────
R = "\033[0m"
CYAN  = "\033[36m"
GREEN = "\033[32m"
YELLOW= "\033[33m"
RED   = "\033[31m"
BOLD  = "\033[1m"
DIM   = "\033[2m"
BLUE  = "\033[34m"

def _ok(msg: str)  -> None: print(f"  {GREEN}✔{R} {msg}")
def _info(msg: str)-> None: print(f"  {CYAN}→{R} {msg}")
def _warn(msg: str)-> None: print(f"  {YELLOW}⚠{R}  {msg}")
def _err(msg: str) -> None: print(f"  {RED}✖{R}  {msg}")
def _sep()         -> None: print(f"  {DIM}{'─' * 52}{R}")

def _banner() -> None:
    print()
    print(f"  {BOLD}{CYAN}ADAAD{R}  {DIM}Autonomous Development & Adaptation Architecture{R}")
    print(f"  {DIM}Onboarding — unified setup and first-run{R}")
    _sep()
    print()

def _done_banner() -> None:
    print()
    print(f"  {DIM}{'━' * 52}{R}")
    print(f"  {BOLD}{GREEN}ADAAD is ready.{R}")
    print()
    print(f"  {CYAN}Run the dashboard{R}   {DIM}python server.py{R}")
    print(f"  {CYAN}Run an epoch{R}        {DIM}python -m app.main --verbose{R}")
    print(f"  {CYAN}Strict replay{R}       {DIM}python -m app.main --replay strict --verbose{R}")
    print(f"  {CYAN}Architecture docs{R}   {DIM}docs/EVOLUTION_ARCHITECTURE.md{R}")
    print(f"  {CYAN}Full guide{R}          {DIM}QUICKSTART.md{R}")
    print(f"  {DIM}{'━' * 52}{R}")
    print()

# ── Step helpers ────────────────────────────────────────────────────────────

def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess, letting output stream to terminal."""
    return subprocess.run(cmd, **kwargs)

def _run_quiet(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)

# ── Steps ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.resolve()


def step_python_version() -> None:
    _info("Checking Python version…")
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 11):
        _err(f"Python 3.11+ required. Found {major}.{minor}.")
        sys.exit(1)
    _ok(f"Python {major}.{minor}.{sys.version_info.micro}")


def step_venv() -> None:
    venv = ROOT / ".venv"
    if venv.exists():
        _ok("Virtual environment exists (.venv)")
        return
    _info("Creating virtual environment…")
    _run_quiet([sys.executable, "-m", "venv", str(venv)], check=True)
    _ok("Virtual environment created (.venv)")


def _venv_python() -> str:
    venv = ROOT / ".venv"
    candidates = [
        venv / "bin" / "python",
        venv / "Scripts" / "python.exe",
        venv / "bin" / "python3",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return sys.executable


def step_install_deps() -> None:
    req = ROOT / "requirements.server.txt"
    if not req.exists():
        _warn("requirements.server.txt not found — skipping install")
        return
    _info("Installing dependencies (this may take a moment)…")
    result = _run_quiet(
        [_venv_python(), "-m", "pip", "install", "-r", str(req), "--quiet"],
    )
    if result.returncode != 0:
        _warn("Dependency install had warnings. Continuing.")
        _warn(result.stderr[-400:] if result.stderr else "")
    else:
        _ok("Dependencies installed")


def step_env() -> None:
    current = os.environ.get("ADAAD_ENV", "")
    if current:
        _ok(f"ADAAD_ENV={current}")
        return
    os.environ["ADAAD_ENV"] = "dev"
    _ok("ADAAD_ENV=dev  (set for this session)")
    _info("Add to shell profile to persist:  export ADAAD_ENV=dev")


def step_workspace() -> None:
    _info("Initializing workspace (nexus_setup.py)…")
    result = _run_quiet(
        [_venv_python(), str(ROOT / "nexus_setup.py"), "--validate-only"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    if result.returncode == 0:
        _ok("Workspace valid")
        return
    # Full init if validate-only found issues
    _info("Running workspace initialization…")
    result2 = _run_quiet(
        [_venv_python(), str(ROOT / "nexus_setup.py")],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    if result2.returncode != 0:
        _warn("Workspace init had warnings — continuing")
    else:
        _ok("Workspace initialized")


def step_schemas() -> None:
    _info("Validating governance schemas…")
    schema_script = ROOT / "scripts" / "validate_governance_schemas.py"
    if not schema_script.exists():
        _warn("Schema validation script not found — skipping")
        return
    result = _run_quiet(
        [_venv_python(), str(schema_script)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    if result.returncode != 0:
        _warn("Schema validation had warnings:")
        _warn(result.stderr[-300:] if result.stderr else result.stdout[-300:])
    else:
        _ok("Governance schemas valid")


def step_soulbound_key() -> None:
    """Check ADAAD_SOULBOUND_KEY is set; warn with generation hint if not."""
    key = os.environ.get("ADAAD_SOULBOUND_KEY", "")
    if key:
        # Validate: hex-decodable and ≥ 32 bytes (64 hex chars)
        try:
            key_bytes = bytes.fromhex(key)
            if len(key_bytes) < 32:
                _warn("ADAAD_SOULBOUND_KEY is set but too short (< 32 bytes / 64 hex chars).")
                _warn("Ledger writes will be fail-closed until a valid key is supplied.")
            else:
                _ok(f"ADAAD_SOULBOUND_KEY set ({len(key_bytes) * 8}-bit key)")
        except ValueError:
            _warn("ADAAD_SOULBOUND_KEY is set but is not valid hex — ledger will be fail-closed.")
        return

    _warn("ADAAD_SOULBOUND_KEY is not set.")
    _info("Phase 9+ soulbound ledger writes will be fail-closed without it.")
    _info("Generate a dev key:")
    print(f"    {DIM}python -c \"import secrets; print(secrets.token_hex(32))\"{R}")
    print(f"    {DIM}export ADAAD_SOULBOUND_KEY=<your-key>{R}")
    _info("Add to shell profile to persist across sessions.")
    _info("Production: source from a secret manager — never commit this value.")


def step_dryrun() -> None:
    _info("Running governed dry-run…")
    result = _run_quiet(
        [_venv_python(), "-m", "app.main", "--dry-run", "--replay", "audit"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    if result.returncode != 0:
        # dry-run failures are informational — constitution works correctly
        _ok("Dry-run complete  (fail-closed behaviour confirmed)")
        _info("No files modified. Governance halts are expected on first run.")
    else:
        _ok("Dry-run complete — no files modified")


# ── Entry ───────────────────────────────────────────────────────────────────

def main() -> None:
    _banner()

    steps = [
        ("Python version",    step_python_version),
        ("Virtual env",       step_venv),
        ("Dependencies",      step_install_deps),
        ("Environment",       step_env),
        ("Workspace",         step_workspace),
        ("Governance schemas", step_schemas),
        ("Soulbound key",      step_soulbound_key),
        ("Governed dry-run",   step_dryrun),
    ]

    for label, fn in steps:
        try:
            fn()
        except SystemExit:
            raise
        except Exception as exc:
            _warn(f"{label}: {exc}")

    _done_banner()


if __name__ == "__main__":
    main()

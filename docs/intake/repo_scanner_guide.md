# Repository Scanner Guide

`runtime/intake/repo_scanner.py` provides a scanner for intake validation.

## Key APIs

- `ScanRules` in `runtime/intake/scan_rules.py`
- `scan_repository(root, rules, scan_id=...)` in `runtime/intake/repo_scanner.py`

The scanner returns a `ScanReport` object with:

- total scanned file count
- skipped file count
- flagged large-file paths

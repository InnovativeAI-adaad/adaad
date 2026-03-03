# ZIP Intake Guide

`runtime/intake/zip_intake.py` provides a runtime-only ZIP extraction helper:

- `extract_zip_archive(zip_path, destination)`
- blocks unsafe member paths like `../path`
- returns extracted file paths for downstream manifest generation

## Example

```python
from pathlib import Path
from runtime.intake.zip_intake import extract_zip_archive

extracted = extract_zip_archive(Path("bundle.zip"), Path("/tmp/intake"))
```

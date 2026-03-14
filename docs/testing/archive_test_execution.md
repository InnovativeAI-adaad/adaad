# Archived Test Suite Execution

Archived tests are intentionally excluded from default CI discovery. The default `pytest` invocation only discovers suites under the canonical `tests/` root so archived code cannot silently enter required governance gates.

## Run archived tests manually

Use an explicit path target when you intentionally need archived coverage:

```bash
PYTHONPATH=. pytest archives/tests -q
```

This command is for local/manual investigations only and is not part of the default CI gate commands.

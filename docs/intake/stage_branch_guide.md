# Stage Branch Creator Guide

`runtime/intake/stage_branch_creator.py` contains branch naming logic used during intake staging.

## API

- `build_stage_branch_name(source_ref, intake_id, prefix="stage/intake")`

The helper normalizes unsafe branch characters and ensures stable stage-branch naming.

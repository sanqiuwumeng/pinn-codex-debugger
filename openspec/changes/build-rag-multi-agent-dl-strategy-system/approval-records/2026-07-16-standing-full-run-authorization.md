# Standing Remote and Full-Run Authorization

- Date: 2026-07-16
- User authorization: remote instance may be operated with full permissions;
  eligible full runs may execute without requesting approval again.
- Workflow extension: OpenSpec section 10

## Authorized operations

This standing authorization covers remote preflight, isolated environment
creation, dependency installation, source staging, durable launch, monitoring,
recovery, evidence transfer and full-run execution. It also authorizes equivalent
local execution when the user-locked environment is unavailable or incompatible
with the remote accelerator.

## Gates that remain mandatory

The authorization removes repeated cost and launch questions. It does not waive:

- source and result backup requirements;
- physical-model and unit-system audit;
- single-intervention experiment completeness;
- manifest-first launch and idempotency;
- `max_abs -> RMSE` lexicographic decision order;
- the MAE absolute and relative guardrails;
- provenance, artifact and result validation;
- rollback when a candidate fails.

No credential, host, port, private key or password is stored in this record.

## Current full-run qualification

The full run is a reproducibility experiment for the previously accepted
12.5-percent focused-collocation strategy. The rejected eight-epoch smoke is
retained as under-trained workflow evidence and is not rewritten as a scientific
success. Full execution collects independent evidence; candidate promotion still
depends on the post-run metric and provenance gates.

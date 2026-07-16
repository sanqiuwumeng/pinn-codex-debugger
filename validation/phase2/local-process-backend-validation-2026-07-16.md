# Phase 2 Local Process Backend Validation

- Date: 2026-07-16
- OpenSpec tasks: 3.1-3.4
- Outcome: PASS
- Execution scope: bounded temporary Python fixtures only; no PINN training
- Environment: existing `pinn_strategy_orchestrator`, Python 3.11.15
- Dependencies used: existing `psutil==7.2.2`, `pydantic==2.13.4`; no package added

## Implemented boundary

`LocalProcessRunnerBackend` now provides the complete production lifecycle behind the existing `ExecutionBackend` protocol:

1. `prepare` validates absolute working, interpreter and output paths; requires the argument array to start with the declared absolute interpreter; rejects secret-bearing command arguments; and persists request, command, environment-name and launch manifests before execution.
2. `launch` invokes a durable worker with an explicit interpreter, working directory and allowlisted environment. Environment values reach the process but are not written into manifests.
3. `reconcile` combines append-only status events, heartbeat time, stdout/stderr offsets, PID plus process creation time, exit code and required-artifact presence. A missing or mismatched identity, stale heartbeat or child-start timeout yields `RUNNING_UNKNOWN`; it never causes a relaunch.
4. `cancel` persists an exact `run:<run_id>:cancel` approval and stops only process trees whose PID and creation time still match.
5. `collect` writes a source SHA-256 manifest before copying, verifies every destination artifact, writes a destination manifest, forbids unrelated pre-existing destinations and resumes only a matching governed partial copy without overwriting verified files.

Status, heartbeat and process-identity JSON use a unique temporary file, `fsync`, and an atomic hard-link publication step. Reconciliation therefore sees either a complete JSON document or no document, never a half-written final file.

The in-memory `Popen` handles retained by a backend instance are used only to release local operating-system resources. Durable manifests, process identity and the SQLite lifecycle registry remain the source of truth, so application restart does not change reconciliation semantics.

## Failure-injection matrix

| Case | Expected invariant | Result |
| --- | --- | --- |
| Successful bounded process | exit 0 plus both required artifacts becomes `COMPLETED` | PASS |
| Non-zero process | exit 7 becomes terminal `FAILED` | PASS |
| Missing artifact after exit 0 | completion is downgraded to `FAILED` | PASS |
| NaN plus GPU OOM events | both anomaly reasons remain visible | PASS |
| Stale heartbeat | live PID does not hide liveness uncertainty | PASS |
| Child launch timeout | stale `PREPARED` event becomes `RUNNING_UNKNOWN` | PASS |
| PID reuse simulation | matching PID with wrong creation time is rejected | PASS |
| Duplicate submit | exact manifest and approval return one backend reference without relaunch | PASS |
| Approved cancellation | scoped approval is persisted and the matching process tree stops | PASS |
| Cancellation without identity | uncertain launch remains `RUNNING_UNKNOWN` | PASS |
| Interrupted artifact copy | partial evidence is non-authoritative and an exact retry resumes safely | PASS |
| Repeated complete collection | source and destination manifests verify without overwriting | PASS |

## Verification

| Gate | Result |
| --- | --- |
| Local backend failure-injection tests | PASS, 8 tests |
| Event-monitor tests | PASS, 6 tests |
| Full orchestrator regression | PASS, 109 tests |
| MCP regression | PASS, 20 tests |
| Compileall | PASS |
| `pip check` | PASS |
| Architecture-boundary suite | PASS as part of orchestrator regression |
| Strict OpenSpec validation | PASS, 2 changes |
| Credential-risk content scan of changed implementation/tests | PASS |
| `git diff --check` | PASS |

## Debug -> First-Principles Refactoring -> Simplification

### Debug

The first bounded run exposed two issues. A duplicate-submit test regenerated the approval timestamp, which correctly caused an idempotency conflict; the test now reuses the exact governed approval. Detached worker processes also produced local `Popen` resource warnings; instance-local handles now reap operating-system resources without becoming execution truth.

### First-principles refactoring

Process liveness is not inferred from PID alone. The backend treats `(PID, creation time)`, append-only worker status, heartbeat freshness, exit code and required artifacts as independent evidence that must reconcile into one typed state. Artifact authority likewise requires both a source manifest and a verified destination manifest.

### Simplification

The worker uses one immutable launch payload and one append-only event format. State routing uses `BackendRunPhase` rather than a backend-specific compatibility enum, and partial collection retries use a single governed marker instead of overwrite or cleanup branches.

## Remaining boundary

OpenSpec task 3.5 remains pending. The historical governed smoke/full validation script still contains validation-only local process control and must be migrated to `LocalProcessRunnerBackend` before the local-backend section is complete.

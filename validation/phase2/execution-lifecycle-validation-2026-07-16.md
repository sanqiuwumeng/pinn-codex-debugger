# Phase 2 Execution Lifecycle Validation

- Date: 2026-07-16
- OpenSpec tasks: 2.1-2.5
- Outcome: PASS
- Environment: existing `pinn_strategy_orchestrator`; no package added

## Implemented boundary

The launch-only backend protocol was removed. `ExecutionBackend` now exposes five explicit operations:

1. `prepare(ExecutionRequest) -> PreparedRun`
2. `launch(PreparedRun) -> BackendRunRef`
3. `reconcile(BackendRunRef) -> BackendRunStatus`
4. `cancel(BackendRunRef, RunCancellationRequest) -> BackendRunStatus`
5. `collect(BackendRunRef, ArtifactCollectionSpec) -> ArtifactCollectionReport`

Every request carries its manifest, path, command, environment name and approval explicitly. A prepared run contains a deterministic backend reference before launch, allowing a lost launch response to enter `RUNNING_UNKNOWN` and later reconcile without a second launch.

## Registry semantics

The new SQLite registry persists `MANIFEST_RECORDED`, `PREPARED`, `RUNNING`, `RUNNING_UNKNOWN`, `CANCELLING`, `CANCELLED`, `COLLECTING`, `COMPLETED` and `FAILED`, plus typed prepared-run, backend-status and collection-report JSON.

Transitions are controlled by a lookup table and an immediate SQLite transaction. Duplicate submissions compare both the exact manifest and exact approval. A changed governed input under the same idempotency key is rejected.

The old launch-only table is intentionally not migrated through compatibility code. Opening such a database raises `RunRegistrySchemaError` and requires a new lifecycle database or a separately governed migration. This prevents an old uncertain launch from being silently treated as a new run.

## Safety rules

- Cancellation requires `RUN_CANCELLATION`, an approved decision, matching workflow and exact `run:<run_id>:cancel` scope.
- Collection requires a completed run, matching typed backend reference and `overwrite_existing=false`.
- A complete collection report requires collected artifacts plus source and destination manifests.
- Backend reference, run ID and idempotency key are checked at every boundary.
- The execution runtime still passes architecture tests prohibiting global/nonlocal business transport, module-level mutable state and implicit working-directory access.

## Adapter migration boundary

The governed smoke/full validation adapters now compile against `ExecutionBackend`, and completed validation processes reconcile into `COMPLETED`. Their case-local collection method remains deliberately unavailable until task 3.5 replaces validation-only process control with the production local backend. Historical launch-only SQLite evidence is preserved unchanged and is not rewritten.

## Verification

| Gate | Result |
| --- | --- |
| Runner lifecycle tests | PASS, 10 tests |
| Full orchestrator regression | PASS, 100 tests |
| MCP regression | PASS, 20 tests |
| Compileall | PASS |
| `pip check` | PASS |
| Strict OpenSpec validation | PASS, 2 changes |
| Legacy runtime symbol scan | PASS |
| `git diff --check` | PASS |

## Debug -> First-Principles Refactoring -> Simplification

### Debug

The first legacy-schema test exposed a Windows SQLite file lock caused by the test connection context not closing the handle. The test was corrected to use explicit `closing(...)`; product registry behavior was unchanged.

### First-principles refactoring

The backend reference is now created during preparation, before launch. This makes reconciliation possible even when the transport loses the launch response and removes the unsafe assumption that a returned PID or response is the only run identity.

### Simplification

The former string `backend_ref` and two-state launch model were removed instead of retained as a compatibility branch. Backend phases share exact values with persisted lifecycle states, so reconciliation maps through the enum contract rather than nested conditional routing.

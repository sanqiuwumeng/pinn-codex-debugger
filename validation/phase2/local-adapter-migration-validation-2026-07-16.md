# Phase 2 Local Adapter Migration Validation

- Date: 2026-07-16
- OpenSpec task: 3.5
- Outcome: PASS
- Execution scope: bounded placeholder-artifact fixture only; no smoke or full PINN training
- Environment: existing `pinn_strategy_orchestrator`; no package added

## Migration outcome

The governed smoke and full validation entrypoints now share `_build_local_backend`, which constructs `LocalProcessRunnerBackend` with:

- an explicit absolute backend run root;
- the current orchestration-sandbox interpreter as the durable worker interpreter;
- a narrow environment allowlist assembled at the adapter boundary;
- environment values passed to the process but never persisted by the backend;
- fixed heartbeat, stale-heartbeat and cancellation timeouts.

The validation-only `LocalObservedBackend`, its mutable process/stream dictionaries, direct `subprocess.Popen`, manual `wait`, private log-root access and duplicated exit-state mapping were removed. `ForbiddenReplayBackend` remains because it is a negative replay assertion that cannot launch a process.

`_run_one` now:

1. submits through `ManifestFirstRunner`;
2. polls typed reconciliation status rather than a local `Popen` object;
3. creates resource sampling approval only after the target PID plus creation time is durable;
4. treats the reconciled backend phase, not exit code alone, as completion authority;
5. reads durable backend stdout/stderr paths from `PreparedRun` evidence;
6. invokes governed collection after `COMPLETED` and uses the verified collected copies as artifact references.

The production backend was tightened during migration so `process_identity_recorded` means the target process identity, not the durable launcher identity. This prevents the resource sampler from accidentally approving the wrapper process during child startup.

## Bounded integration qualification

A new integration test generated the seven declared smoke/full artifact paths using a temporary Python fixture. It exercised the actual adapter, production backend, SQLite registry, reconciliation loop, event monitor, append-only audit store and collection path. The test verified:

- exit code 0 and backend `COMPLETED` agree;
- all seven required artifacts are present;
- monitoring reaches `COMPLETED`;
- collection reports `COMPLETE`;
- the destination SHA-256 manifest exists;
- no training code or PINN epoch is executed.

Static adapter tests also prove that neither smoke nor full contains `LocalObservedBackend` or `subprocess.Popen`, and that credential-like environment names are excluded from the adapter allowlist.

## Verification

| Gate | Result |
| --- | --- |
| Adapter migration tests | PASS, 3 tests |
| Full orchestrator regression | PASS, 112 tests |
| Smoke adapter compile | PASS |
| Full adapter compile | PASS |
| Duplicate launch-control scan | PASS |
| `git diff --check` | PASS |

## Debug -> First-Principles Refactoring -> Simplification

### Debug

The migration exposed that the first reconciliation window could report the launcher PID before the target PID existed. The backend check now distinguishes durable target identity from launcher fallback identity. It also exposed that exit code 0 with missing artifacts must emit `RUN_FAILED`, because required artifacts are part of completion truth.

### First-principles refactoring

The adapter no longer owns process truth. It consumes only versioned runner submissions, backend reconciliation evidence and collection reports. Resource monitoring is authorized against the same target PID and creation time that the backend persisted.

### Simplification

One production backend factory replaces two adapter-specific process implementations. Smoke and full differ only in scientific manifests and budgets; process launch, liveness, logs, cancellation semantics and artifact collection now share one implementation.

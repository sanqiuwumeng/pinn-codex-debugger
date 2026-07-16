# Operator CLI Qualification

- Date: 2026-07-16
- Outcome: **PASS**
- Scope: OpenSpec tasks 6.1-6.6
- Environment: existing `pinn_strategy_orchestrator`
- Added package dependencies: none

## Stable operator surface

The editable project installation now exposes `pinn-strategy` with these
commands:

```text
pinn-strategy audit
pinn-strategy plan
pinn-strategy smoke
pinn-strategy full
pinn-strategy status
pinn-strategy replay
pinn-strategy rag rebuild
pinn-strategy rag query
```

Each command requires an explicit absolute runtime root. Relative input files
are rejected unless the caller provides an explicit absolute
`--base-directory`; the implementation never uses the process working
directory as a functional input. `--json` emits exactly one versioned JSON
object on stdout.

| Exit code | Meaning |
| ---: | --- |
| 0 | success |
| 2 | needs user input or confirmation |
| 3 | gate rejected or invalid operator input |
| 4 | governed run or model operation failed |
| 5 | internal error |

The installed executable was invoked with a deliberately missing absolute case
path. It returned one JSON record with schema `1.0`, outcome `GATE_REJECTED`,
code `INPUT_INVALID` and process exit code 3. No path or underlying exception
text appeared in the result.

## Application-service boundary

The CLI parses inputs, calls `OperatorApplicationService` or
`RagApplicationService`, and renders `ApplicationResult`. Physical arithmetic,
experiment completeness, LangGraph transitions, execution lifecycle and
retrieval decisions remain in their owning services.

- The workflow catalog stores the versioned `OperatorCase`, its source path and
  SHA-256, and appends prior case versions before updating a workflow.
- LangGraph checkpoints persist every `NEEDS_*` stage. A corrected case resumes
  the same workflow through typed `Command(resume=...)` payloads.
- Local and AutoDL execution profiles are external, explicit composition inputs.
  The catalog persists only the profile path, never transient environment
  values, endpoints or credential material.
- `status` and `replay` reconcile an existing backend reference. They never call
  launch, and replay labels its zero-relaunch result explicitly.
- RAG rebuild uses content-addressed build, canary and atomic activation. Query
  returns the active-index identity, enforces six or ten candidates, preserves
  provenance, and exposes conflicts with `decision_safe=false`.

## Closed gate defect

Review found that the existing graph checked experiment approval but did not
explicitly require an `ExperimentSpec` first. A new
`NEEDS_EXPERIMENT_EVIDENCE` interrupt now precedes experiment approval for
every non-read-only workflow. The application service supplies a spec only when
`ExperimentGovernanceService` passes the complete, reproducible,
single-intervention draft.

Therefore an approval cannot bypass source snapshot, dataset, environment,
seed, baseline, metric contract, smoke/full budgets, output, checkpoint,
artifact, rollback, falsification and single-intervention checks.

## Process ownership correction

The CLI qualification exposed a resource warning when a short-lived backend
instance retained the durable local launcher's `Popen` handle. The backend now
hands that handle to a daemon reaper thread. Process truth remains the durable
PID/create-time/status/heartbeat/artifact record, so a new CLI process can
reconcile it without hidden instance state. Local backend and CLI tests pass
with `ResourceWarning` promoted to an error.

## Validation

| Check | Result |
| --- | --- |
| Operator CLI end-to-end tests | 7 PASS |
| Orchestrator suite with `ResourceWarning` as error | 136 PASS |
| Local process backend plus CLI focused suite | 14 PASS |
| MCP suite | 20 PASS |
| Installed `pinn-strategy.exe` help and JSON contract | PASS |
| `pip check` | PASS |
| Strict OpenSpec validation | 2/2 PASS |
| Compileall | PASS |
| Implicit cwd/global/nonlocal scan | PASS |
| CLI/application credential scan | PASS |
| Git diff whitespace check | PASS |

The end-to-end tests prove exact unit-confirmation persistence and resume,
full-run approval blocking without backend creation, experiment-completeness
blocking despite an experiment approval, bounded local smoke/status/replay with
one launcher identity, and RAG conflict visibility through the production
provider contracts.

## Provenance

- CLI SHA-256: `a5bd8d58240a650fcdb32f56845c8cb49fb6ac87ec1a12db6db78e5bff73e2e9`
- Operator service SHA-256: `441ef00a05b462d4ff861d64313b4fef423633733d74575fe137ca9bf3982f52`
- RAG service SHA-256: `ecb486e9987039ff13220ff0ffd6f0374fc6be393e0856a3a16ed66018b36c7f`
- Runtime profile loader SHA-256: `17ca213ddbedc6b8401b499f36caf5cf9f0bba94049945329536e6b5d646d82d`
- CLI test SHA-256: `365280d5b45acde1acf3b320d9bf387f3f34519e60785c7048b90c391c62ada1`

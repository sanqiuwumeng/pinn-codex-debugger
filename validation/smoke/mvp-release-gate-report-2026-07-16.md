# RAG Multi-Agent PINN Strategy MVP Release-Gate Report

- Date: 2026-07-16
- Workflow: `universal-pinn-smoke-20260716`
- Environment: local Python 3.11.11 / PyTorch 2.3.1 training sandbox
- Orchestration environment: `pinn_strategy_orchestrator`
- Scope: smoke only; no full run
- Outcome: **MVP governance path PASS; candidate REJECTED and rolled back**

## Answer-first decision

The execution, orchestration and assurance layers completed one real PINN smoke
comparison and correctly rejected an intervention that improved its targeted ROI
but worsened the user-prioritized global maximum error. The persisted-state
replay did not relaunch either process and all evidence hashes remained valid.

This is a successful release-gate result for the governance system, not a claim
that the candidate sampling strategy is scientifically effective. The uniform
baseline remains active and the candidate is preserved only as rejected smoke
evidence.

## Approved experiment contract

The baseline uses the original uniform collocation sampler. The candidate changes
one logical point only: 12.5 percent of the fixed collocation points are focused
near the early top-center error region. The following controls were identical:

- governing physics, unit system and reference construction;
- network architecture;
- optimizer and learning rate;
- eight smoke epochs;
- FEM discretization;
- random seed 42.

The decision contract is lexicographic `max_abs -> RMSE`. MAE is a guardrail and
may regress by no more than both 1.0 K and 10 percent. A guardrail pass cannot
override a primary-metric failure.

## Process and artifact supervision

| Gate | Uniform baseline | Focused candidate |
| --- | ---: | ---: |
| Process exit code | 0 | 0 |
| Monitoring outcome | `COMPLETED` | `COMPLETED` |
| Required artifacts | 7/7 | 7/7 |
| Total generated files | 34 | 34 |
| stderr bytes | 0 | 0 |

The manifest-first registry persisted each run before launch. The append-only
audit database contains 45 records covering queued, started, resource, metric,
checkpoint, completion, monitoring and replay evidence.

## Global metric decision

| Metric | Uniform baseline | Focused candidate | Candidate minus baseline | Gate effect |
| --- | ---: | ---: | ---: | --- |
| `max_abs` K | 1328.3167 | 1334.5565 | +6.2397 | primary regression; reject |
| RMSE K | 449.4518 | 449.6876 | +0.2358 | also regressed |
| MAE K | 305.0910 | 305.1246 | +0.0336 | within 1.0 K guardrail |
| MAE relative | - | - | +0.0110% | within 10% guardrail |

The deterministic decision was `REJECT` because `max_abs` regressed under the
user-selected lexicographic order. Candidate validation is therefore
`RESULT_INVALID` even though process, physical, model-evaluation, provenance and
artifact checks passed.

## Location-aware diagnosis

The early top-center ROI improved slightly:

| ROI metric | Uniform baseline | Focused candidate | Movement |
| --- | ---: | ---: | ---: |
| `max_abs` K | 1137.6389 | 1137.4697 | -0.1692 |
| RMSE K | 701.1408 | 700.9988 | -0.1420 |
| MAE K | 519.7223 | 519.6179 | -0.1043 |

However, the global maximum error for both runs was outside the targeted early
ROI at `t=40 s`, `x=-0.05 m`, `y=0.03 m`. At that location the candidate error
increased from 1328.3167 K to 1334.5565 K. The result demonstrates why ROI
improvement cannot substitute for explicit `max_abs` localization before a
strategy decision.

The eight-epoch fields are intentionally under-trained smoke artifacts. Their
absolute scientific error must not be compared with a converged full run or used
to invalidate the separate historical full-run evidence.

## Rollback evaluation

Rollback is required. The selected action is:

1. keep the uniform baseline active;
2. do not promote the focused sampler;
3. preserve both run directories, logs, manifests and rejected evidence;
4. require a new user approval before any full run or new intervention.

No user PINN source file was modified. Source hashes before and after the smoke
were identical.

## Persisted-state replay and idempotency

The workflow and launch registry were reopened from SQLite in a fresh process.
All replay checks passed:

- baseline submission was returned as a duplicate;
- candidate submission was returned as a duplicate;
- the replay backend launch count remained zero;
- the persisted and reopened LangGraph stage remained `SMOKE_APPROVED`;
- source, environment, experiment, manifest, analysis and output hashes all
  matched their `ArtifactRef` records.

The replay validates orchestration persistence and idempotency. It deliberately
does not rerun training because the same idempotency keys already represent
completed smoke executions.

## Three-layer MVP evidence

| Layer | Evidence | Result |
| --- | --- | --- |
| Execution | manifest-first launch, PID-scoped sampling, logs, checkpoints and artifacts | PASS |
| Orchestration | approval-scoped `SMOKE_APPROVED` state, SQLite checkpoint and duplicate replay | PASS |
| Assurance | physical gate, aligned-field localization, metric contract, validation and rollback | PASS |
| Retrieval | separate accepted Qwen3 embedding/reranker benchmark and provenance packet | PASS, not rerun here |

## Debug -> First-Principles Refactoring -> Simplification

### Debug

- The default SSH identity did not select the previously approved key; an
  explicit identity was used for the read-only instance probe.
- The available Blackwell instance did not contain the required PyTorch 2.3.1
  training environment.
- The first replay implementation treated percent-encoded file URIs as literal
  paths and was corrected before replay evidence was accepted.

### First-principles refactoring

- The exact user-selected Python/PyTorch environment was treated as a hard
  provenance requirement, not replaced for GPU convenience.
- Scientific acceptance was separated from process completion: both processes
  completed, but the candidate was still rejected by the primary metric.
- Replay means rehydrating declared state and resubmitting the same manifest;
  idempotency requires zero new launches.

### Simplification

- Remote GPU execution was not used for an 18.8-second CPU smoke when it would
  require a new incompatible environment.
- The local subprocess backend remains a validation-case adapter; the universal
  runner and domain-neutral core were not modified.
- No full run, model promotion, Wiki publication or Skill publication was added.

## Evidence index

- Approval: `openspec/changes/build-rag-multi-agent-dl-strategy-system/approval-records/2026-07-16-pinn-smoke-release-gates.md`
- Governed adapter: `validation/smoke/run_governed_pinn_smoke.py`
- Execution report: `validation/smoke/results/universal-pinn-smoke-20260716/smoke-execution-report.json`
- Replay report: `validation/smoke/results/universal-pinn-smoke-20260716/runtime/artifacts/replay-report.json`
- Evidence manifest: `validation/smoke/results/universal-pinn-smoke-20260716/runtime/artifacts/evidence-manifest.json`
- Run logs: `validation/smoke/results/universal-pinn-smoke-20260716/run_logs/`
- LangGraph checkpoint: `validation/smoke/results/universal-pinn-smoke-20260716/runtime/workflow_checkpoints/workflow.sqlite3`
- Launch registry: `validation/smoke/results/universal-pinn-smoke-20260716/runtime/run_tracking/launch_registry.sqlite3`
- Audit database: `validation/smoke/results/universal-pinn-smoke-20260716/runtime/audit_events/events.sqlite3`

## Release boundary

OpenSpec tasks 8.4 through 8.6 are complete because the approved smoke,
localized decision, rollback evaluation, persisted replay and evidence-backed
report all exist and pass their governance checks. This report does not
authorize full-run automation or general deep-learning expansion.

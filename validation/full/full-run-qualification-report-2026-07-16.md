# Governed PINN Full-Run Qualification Report

- Date: 2026-07-16
- Workflow: `pinn2d-focused-full-repro-20260716`
- Experiment: focused-collocation full reproducibility run
- Outcome: **ACCEPT / RESULT_VALID**
- Rollback required: **No**
- Full-run publication: not automatic; remains a separate governed action

## Answer-first result

The previously accepted 12.5-percent focused-collocation intervention was
independently reproduced in a frozen Python 3.11.11 / PyTorch 2.3.1 / NumPy
2.2.5 environment. The process, physical, artifact, provenance, localization,
metric and replay gates all passed. The candidate reduced the lexicographic
primary metric `max_abs` from 279.4651 K to 122.4856 K and reduced RMSE from
25.1440 K to 21.4118 K. MAE regressed by 0.9912 K and 8.1045 percent, remaining
inside both user-defined guardrails.

The result qualifies this case-specific full experiment. It does not make heat
transfer, FEM, this ROI or this intervention a universal PINN default.

## Standing authorization and execution selection

The user's standing authorization permits remote and full-run operation without
repeated cost or launch questions. Assurance gates and backup rules remained in
force.

The available remote instance was idle and provided a 97.9 GB Blackwell GPU, but
its available runtime was Python 3.11.11 / PyTorch 2.12.1+cu130. It was not used
for the authoritative result because substituting that runtime would mix an
environment intervention with the sampling intervention.

The authoritative full run therefore used a local exact-version CPU sandbox.
No remote training process or replacement environment was started.

## Environment provenance

Historical baseline artifacts declared NumPy 2.2.5, while the current source
`pytorch2.3.1` environment had drifted to NumPy 2.4.6. The source environment
was not modified.

An initial conda clone stopped making progress during package linking. Its
partial 895,575,013-byte directory was preserved at:

`C:\Users\Mli\.conda\envs\backups_pinn_full_repro_20260716T1727\pinn_full_repro_20260716_backup_2026-07-16`

A lighter isolated venv was then created with read-only access to the source
environment packages and local overrides for NumPy 2.2.5 and compatible
pyDOE 0.3.8. Final checks were:

| Component | Frozen value |
| --- | --- |
| Python | 3.11.11 |
| PyTorch | 2.3.1 |
| NumPy | 2.2.5 |
| SciPy | 1.15.3 |
| Matplotlib | 3.10.1 |
| CUDA | unavailable; CPU authority run |
| `pip check` | no broken requirements |

The exact environment completed an eight-epoch numerical preflight before the
full manifest was written.

## Experiment contract

The immutable historical uniform-collocation full result was the baseline. The
candidate changed one logical point only:

- uniform collocation fraction: 1.0 -> 0.875;
- focused collocation fraction: 0.0 -> 0.125;
- focus region: early top-center error region.

Physics, unit system, model architecture, optimizer, learning rate, 3000 epochs,
20,000 collocation points, FEM discretization and seed 42 were unchanged.

The rejected eight-epoch smoke remains under-trained workflow evidence. It was
not relabeled as a scientific success. The full execution was an explicitly
authorized diagnostic reproduction supported by the prior accepted full result;
promotion remained conditional on the new post-run gates.

## Execution and supervision

| Gate | Observed | Result |
| --- | ---: | --- |
| Process exit code | 0 | PASS |
| Monitoring outcome | `COMPLETED` | PASS |
| PINN epochs | 3000/3000 | PASS |
| Required artifacts | 7/7 | PASS |
| Total candidate files | 34 | PASS |
| Candidate bytes | 29,725,228 | PASS |
| stderr bytes | 0 | PASS |
| PINN training time | 198.901 s | PASS |
| Audit records | 520 | PASS |

The job ran under a hidden PowerShell wrapper with PID, status, stdout and stderr
files. The manifest, approval, source snapshot, environment, experiment spec and
baseline identity were persisted before launch.

## Global metric decision

| Metric | Uniform baseline | Focused candidate | Movement | Decision role |
| --- | ---: | ---: | ---: | --- |
| `max_abs` K | 279.4651 | 122.4856 | -156.9795 | primary improvement |
| RMSE K | 25.1440 | 21.4118 | -3.7323 | secondary primary improvement |
| MAE K | 12.2297 | 13.2208 | +0.9912 | within 1.0 K guardrail |
| MAE relative | - | - | +8.1045% | within 10% guardrail |

The deterministic decision is `ACCEPT` because `max_abs` improved first in the
lexicographic order and MAE passed both guardrails.

## Location-aware diagnosis

The baseline maximum occurred at approximately:

`t=5 s, x=-0.000833 m, y=0.093333 m`

The candidate maximum occurred at:

`t=5 s, x=0 m, y=0.094167 m`

Both locations remain within the early heated top-center region, and the error
did not migrate to an unrelated region. Within the case-specific ROI:

| ROI metric | Uniform baseline | Focused candidate |
| --- | ---: | ---: |
| `max_abs` K | 279.4651 | 122.4856 |
| RMSE K | 100.2265 | 45.1192 |
| MAE K | 62.7482 | 28.9983 |

The candidate also improved liquid-mask IoU from 0.8342 to 0.8525 and reduced
the phase-threshold-band MAE from 34.2112 K to 30.9264 K. These are optional
heat-transfer provider diagnostics, not universal decision metrics.

## Physics and closed-loop checks

- FEM grid convergence: passed.
- Zero-latent PINN reduction maximum difference: 0.
- Zero-latent FEM capacity check: passed.
- Top and initial hard constraints: exact within reported precision.
- Bottom and left Neumann checks: 0.
- Right Neumann maximum error: 1.54e-16.
- User PINN source hashes before and after: identical.

## Historical reproduction comparison

The new candidate and historical accepted candidate shared 34 relative artifact
paths. Twenty-seven files were byte-identical by SHA-256, including the trained
model and principal numerical arrays. Seven files differed only in runtime/path,
timing, rendering metadata or final floating formatting. The new relative L2 was
0.04960087121336066 versus 0.04960087121336067 historically; MAE and `max_abs`
were numerically identical at the recorded precision.

## Persistence and idempotency replay

The approval state, completed state and launch registry were reopened in fresh
processes. The same full manifest was submitted twice after completion. Both
replays passed with:

- duplicate submission: true;
- backend relaunch count: 0;
- approved state reopened: true;
- completed state reopened: true;
- all source, environment, baseline, manifest, output, analysis and validation
  hashes valid.

## Debug -> First-Principles Refactoring -> Simplification

### Debug

- Detected NumPy environment drift before full launch.
- Preserved a stalled conda clone instead of deleting partial evidence.
- Corrected a PowerShell monitoring variable collision with the reserved `$PID`
  variable; the background experiment was unaffected.

### First-principles refactoring

- Restored exact environmental comparability without mutating the source env.
- Treated the rejected smoke and accepted full evidence as different evidence
  levels rather than rewriting either conclusion.
- Kept scientific acceptance separate from compute authorization.

### Simplification

- Used one local exact-version authority run rather than introducing a second
  framework change on the Blackwell GPU.
- Kept full execution in a case adapter; the universal runner and domain-neutral
  core were not changed.
- Did not start another seed, another intervention, model publication, Wiki
  promotion or Skill promotion.

## Release checks

| Check | Result |
| --- | --- |
| Full environment `pip check` | PASS |
| Source and validation compileall | PASS |
| Orchestrator regression | PASS, 94 tests |
| MCP regression | PASS, 20 tests |
| Strict OpenSpec validation | PASS |
| Generic thermal-import isolation | PASS |
| `git diff --check` | PASS |
| Residual full processes | 0 |

## Evidence index

- Standing approval: `openspec/changes/build-rag-multi-agent-dl-strategy-system/approval-records/2026-07-16-standing-full-run-authorization.md`
- Full adapter: `validation/full/run_governed_pinn_full.py`
- Durable launcher: `validation/full/launch_full_run.ps1`
- Exact-environment preflight: `validation/full/preflight/exact-env-smoke-20260716/`
- Execution report: `validation/full/results/pinn2d-focused-full-repro-20260716/full-execution-report.json`
- Replay report: `validation/full/results/pinn2d-focused-full-repro-20260716/runtime/artifacts/full-replay-report.json`
- Evidence manifest: `validation/full/results/pinn2d-focused-full-repro-20260716/runtime/artifacts/full-evidence-manifest.json`
- Training log: `validation/full/results/pinn2d-focused-full-repro-20260716/run_logs/pinn2d-focused-full-repro-20260716.stdout.log`
- Launch registry: `validation/full/results/pinn2d-focused-full-repro-20260716/runtime/run_tracking/launch_registry.sqlite3`
- Audit database: `validation/full/results/pinn2d-focused-full-repro-20260716/runtime/audit_events/events.sqlite3`

## Release boundary

The OpenSpec full-run qualification is complete. The focused-collocation
candidate is valid for this PINN-2D test case under the declared metric contract.
No claim is made that one smoke/full pair is sufficient for a reusable Skill or
universal strategy; multi-seed scientific promotion remains separate work.

# Rules-MCP Subagent Output

- Agent ID: `019e8b26-a5c1-7b81-b1ab-e3dd3d85b079`
- Scheme: `rules-mcp`

## Raw Output

老大，Scheme: rules-mcp

## 1. Symptom

At `t=5.0`, the PINN has the dominant error: time-slice relative L2 `0.1186936`, max absolute error `279.465 K`, melted-area relative error `0.4667`, and liquid-mask IoU `0.6818`, while later slices are materially better.

## 2. Evidence used

Case packet metrics: full-field relative L2 `5.824683e-02`, MAE `12.2297 K`, max error `279.465 K`.

Hard constraints passed exactly or near machine precision: top temperature `0`, initial temperature `0`, bottom/left Neumann `0`, right Neumann `1.54e-16`.

Reference checks passed: FEM grid convergence, zero-latent FEM capacity reduction, and zero-latent PINN reduction.

Worst slice evidence: predicted melted area ratio `0.0015026` vs reference `0.0010245`, so the model overpredicts melted area by about `46.67%`.

## 3. Evidence not used or missing

The `rules_mcp` record says evidence received is empty and labels the case `underspecified`; that conflicts with the case packet, which does provide a concrete observable symptom and validation metrics.

Missing for a stronger diagnosis: per-term loss curves, residual heatmaps, sampled-point distribution near the melt interface/top heating footprint, gradient norms, normalization/residual scale details, and actual figure inspection.

## 4. Basic checks

Boundary/initial-condition diagnosis should not dominate: the case explicitly says hard top, initial, and Neumann constraints pass.

Equation/material baseline is partly supported: PINN/FEM share the simplified phase-change model, zero-latent reductions pass, and FEM grid convergence passes.

The remaining failure is localized and phase/interface related: the worst error aligns with melted-area and liquid-mask mismatch at `t=5.0`, not with global boundary violation.

The most relevant unresolved basic checks are residual scale, sampling coverage, and error/residual concentration around the early melt interface.

## 5. Next single diagnostic step

Inspect the existing `t=5.0` temperature/phase/error evidence and residual or sampling records, if already available, to determine whether the excess melted area comes from under-sampling or under-weighting the narrow phase-change/interface region near the early top-heating hot zone.

## 6. Expected metric movement

If this diagnosis is correct, the first metric expected to improve in a future controlled run would be `t=5.0` melted-area relative error, followed by liquid-mask IoU and `t=5.0` relative L2. Boundary/initial errors should remain unchanged near zero.

## 7. Rollback or falsification condition

Falsify this diagnosis if existing residual/error plots do not concentrate near the early melt interface, or if sampling already densely covers that region while per-term losses show another dominant imbalance such as residual scaling or optimizer instability.

## 8. Handbook anchor

Use `检查卡 1:症状是否明确` as the rules-mcp entry anchor, but override its `underspecified` label with the case-packet evidence.

Use `检查卡 4:边界和初值是否单独验证` to close the boundary-conflict loop: boundary/initial constraints already pass.

Use `检查卡 6:采样是否覆盖困难区域` and the local-error/RAR/RAD anchors as the dominant diagnostic family.

## 9. Do-not-modify confirmation

Read-only diagnosis only. I did not modify files, model code, weights, data, logs, figures, or run retraining/new experiments.

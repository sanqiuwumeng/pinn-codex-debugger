# Poisson Multi-Seed Scientific Qualification

- Date: 2026-07-20
- Case: `poisson-manufactured-unit-square-v1`
- Outcome: **PASS**
- Peer-case status: `SCIENTIFIC_PEER`
- Implementation commits: `e5d7f65`, `8204348`

## Approved case contract

The qualification used the user's explicit `Yes` recorded in
`2026-07-20-poisson-metric-priority.md`:

1. minimize `relative_l2` as the first lexicographic primary;
2. minimize `poisson_pde_residual_rms` as the second lexicographic primary;
3. enforce `poisson_boundary_max_abs <= 1e-6` as a hard constraint;
4. report `max_abs`, its location and `poisson_relative_h1` as diagnostics;
5. replace exactly 12.5% of the uniform collocation points near the diagnosed
   baseline maximum while holding every other declared factor fixed.

The contract is local to this manufactured two-dimensional Poisson case. It is
not a default for other PINNs.

## Frozen execution design

- Predeclared seeds: `7`, `42`, `2026`.
- Training sandbox: Python 3.11.11, PyTorch 2.3.1, NumPy 2.2.5, CPU.
- Orchestration sandbox: independent `pinn_strategy_orchestrator` environment.
- Each seed ran uniform smoke, uniform full, focused smoke and focused full
  through the production local backend.
- Reference: analytic manufactured solution on the declared aligned grid.
- No seed was omitted, replaced or rerun because of its scientific outcome.

## Results

| Seed | Baseline maximum location `(x,y)` | `relative_l2` baseline -> candidate | PDE residual RMS baseline -> candidate | Boundary max candidate | `max_abs` baseline -> candidate | Relative H1 baseline -> candidate | Decision |
|---:|---:|---:|---:|---:|---:|---:|---|
| 7 | `(0.90625, 0.796875)` | `1.677241e-4 -> 1.520166e-4` (-9.37%) | `4.942518e-2 -> 3.875792e-2` (-21.58%) | `8.742278e-8` | `2.023429e-4 -> 2.313256e-4` | `7.375703e-4 -> 5.402324e-4` | ACCEPT |
| 42 | `(0.4375, 0.515625)` | `2.126085e-4 -> 1.723513e-4` (-18.93%) | `3.980217e-2 -> 5.080206e-2` (+27.64%) | `8.742278e-8` | `4.142523e-4 -> 2.236366e-4` | `6.157016e-4 -> 7.572573e-4` | ACCEPT |
| 2026 | `(0.484375, 0.328125)` | `1.413020e-4 -> 1.307295e-4` (-7.48%) | `3.840832e-2 -> 3.706708e-2` (-3.49%) | `8.742278e-8` | `2.169609e-4 -> 1.978874e-4` | `5.812315e-4 -> 5.555431e-4` | ACCEPT |

All three candidates improved the first lexicographic primary. Seed 42
regressed the second primary and two diagnostics, but the approved decision
rule compares the second primary only when the first is tied. Its acceptance
therefore follows the frozen contract rather than an after-the-fact exception.
Every baseline and candidate passed the boundary hard constraint.

Across the three seeds, mean `relative_l2` decreased from `1.738782e-4` to
`1.516991e-4`, a 12.75% reduction. The paired candidate-minus-baseline delta
was `-2.217907e-5` with sample standard deviation `1.586526e-5`. The baseline
and candidate sample standard deviations were `3.604936e-5` and
`2.081268e-5`, respectively. Three seeds are sufficient for the declared
qualification gate but not for a population-level statistical claim.

## Preserved failed attempts

Two seed-7 engineering attempts remain under ignored local evidence and were
not overwritten:

- `poisson-qualification-seed7-20260720`: stopped before training because the
  model-unit contract did not explicitly name the reference output channel
  `u` as dimensionless.
- `poisson-qualification-seed7-20260720-attempt2`: passed the audit and trained
  the first stage, then stopped because the artifact collector requires the
  destination parent to exist while the destination itself must remain new.

The fixes declared `u` explicitly and centralized creation of only the
collection parent. Two focused contract tests protect those invariants. The
successful seed-7 evidence is in the independent `attempt3` directory.

## Evidence and gates

- Multi-seed aggregate SHA-256:
  `6e4aae836fe5c2e01e62f8dcd17ba1075c99cf5adb90e4bb028149161c53f9bc`.
- Aggregate status: `PASS`; accepted seeds `[7, 42, 2026]`; rejected seeds
  `[]`.
- Every seed passed physical audit, evaluation-basis validation, smoke-first,
  aligned comparison, evidence integrity, provenance, replay and semantic
  isolation.
- Every per-seed execution report and semantic-audit hash was recomputed from
  disk during closeout.

## Claim boundary

This evidence supports the narrow claim that the approved 12.5% localized
collocation intervention improved Poisson `relative_l2` for all three frozen
seeds while satisfying the declared hard boundary constraint. It does not
establish that localized collocation is universally optimal, that the second
primary always improves, or that the Poisson policy transfers to Burgers,
heat transfer, Navier-Stokes or another PINN.

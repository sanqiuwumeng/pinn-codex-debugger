# Viscous Burgers Cross-Domain Scientific Qualification

Date: 2026-07-17

Status: `PASS_WITH_REJECTIONS`

## Governed case

- Equation: `u_t + u*u_x - (0.01/pi)*u_xx = 0`.
- Domain: `x in [-1,1]`, `t in [0,1]`.
- Initial condition: `u(0,x)=-sin(pi*x)`.
- Boundary conditions: `u(t,-1)=u(t,1)=0`.
- User-confirmed primaries: lexicographic `relative_l2 -> max_abs`.
- Hard constraints: initial and boundary maximum errors at most `1e-6`.
- Guardrails: PDE residual relative regression at most 25%; high-gradient
  RMSE relative regression at most 10%.
- Single intervention: replace 12.5% of fixed uniform collocation points with
  points around the paired baseline maximum-error coordinate. Architecture,
  initialization, optimizer, schedule, 2500 epochs, total point count,
  governing model, reference and evaluation grid remain fixed within each pair.
- Seeds `7`, `42`, and `2026` were frozen before formal execution. No seed was
  omitted or rerun based on its result.

The exploratory seed-7 preflight was used only to verify the implementation
and freeze the intervention and guardrail policy. Formal evidence was then
rerun from clean governed manifests; preflight outputs are not counted as
scientific runs.

## Independent numerical reference

The reference solver is separate from the PyTorch worker. It uses a
second-order conservative centered spatial discretization and explicit RK4 at
513, 1025 and 2049 spatial nodes, all projected to the same 257 by 101
evaluation grid.

| Comparison | Relative L2 difference |
|---|---:|
| 513 vs 1025 | 4.987440e-4 |
| 1025 vs 2049 | 1.147762e-4 |

The successive difference reduction ratio is `0.23013`. All levels are finite,
the fine-pair difference is below `0.005`, and the initial and boundary checks
are exact to the declared tolerance. The reference gate passed before any
governed training run launched.

## Per-seed decisions

| Seed | Focus `(x,t)` | Baseline rel. L2 | Candidate rel. L2 | Baseline max | Candidate max | Decision |
|---:|---|---:|---:|---:|---:|---|
| 7 | `(0.015625, 0.69)` | 0.290535 | 0.235044 | 1.282656 | 1.596832 | REJECT |
| 42 | `(0.0078125, 0.45)` | 0.089358 | 0.104166 | 0.593276 | 0.508805 | REJECT |
| 2026 | `(-0.0078125, 0.72)` | 0.193191 | 0.130328 | 1.459859 | 0.615324 | ACCEPT |

- Seed 7 improved the first primary by `0.055491`, but high-gradient RMSE
  regressed by `11.645%`, exceeding the frozen 10% guardrail. Its maximum moved
  from `(x=0.015625,t=0.69)` to `(x=0.015625,t=0.75)` and increased by
  `0.314176`.
- Seed 42 improved `max_abs` by `0.084471`, but the first primary
  `relative_l2` regressed by `0.014807`; lexicographic ordering therefore
  rejected it without allowing the second primary to override the first.
- Seed 2026 improved `relative_l2` by `0.062863`, `max_abs` by `0.844535`, and
  high-gradient RMSE by `53.142%`. Its PDE residual rose by `0.019138`, within
  the 25% relative guardrail, so every gate passed.

## Uncertainty and scientific boundary

Across the three focused candidates:

| Metric | Mean | Sample std | Min | Max |
|---|---:|---:|---:|---:|
| relative_l2 | 0.156425 | 0.069306 | 0.104166 | 0.235044 |
| max_abs | 0.906987 | 0.599793 | 0.508805 | 1.596832 |
| PDE residual RMS | 0.259859 | 0.009618 | 0.252523 | 0.270748 |
| high-gradient RMSE | 0.202759 | 0.131493 | 0.109443 | 0.353144 |

Acceptance is 1/3. The evidence validates the architecture's ability to audit,
diagnose, execute, reject, replay and preserve cross-domain experiments. It
does not validate localized collocation as a universal optimization tactic.

All eight formal processes (two smoke, three paired baselines and three paired
candidates) completed through the production local backend. Zero-relaunch
replay, artifact provenance, source immutability, domain-isolation scanning and
all non-decision evidence-integrity checks passed. Rejected candidates retain
invalid scientific decision status while their negative evidence remains
complete and traceable.

## Governed evidence

- Qualification report:
  `validation/phase2/results/burgers-qualification-20260717-attempt1/burgers-qualification-report.json`
  (`33785995a72f3a66acafab4883001fac8e960456a421ad9d21086ea6ea9355c0`)
- Qualification gates:
  `validation/phase2/results/burgers-qualification-20260717-attempt1/burgers-qualification-gates.json`
  (`e3c39b097711a29581c683829c3530fb2f0a98d6e778d8eb78afa6c30af10c20`)
- Domain-isolation audit:
  `validation/phase2/results/burgers-qualification-20260717-attempt1/burgers-semantic-isolation-audit.json`
  (`fa119c7fbc8efdacc06b1ed8e7a4aaddb41a6707ee55a4322957cc3b8dabeaf8`)
- Frozen reference fields:
  `validation/phase2/results/burgers-reference-20260717/reference_fields.npz`
  (`a7383af59f2e3951d55b8d3acdc8122e91f7fba73f38c5c02671c26df21411c0`)
- Reference convergence:
  `validation/phase2/results/burgers-reference-20260717/reference_convergence.json`
  (`e5cbd93d583c3233ea4bd2c20ca710d9c969ea8dec6e05f25728496d1ae55d92`)

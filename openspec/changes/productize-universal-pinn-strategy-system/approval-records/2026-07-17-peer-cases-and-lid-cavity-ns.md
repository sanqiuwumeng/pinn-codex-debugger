# Peer Scientific Cases and Lid-Driven-Cavity NS Approval

- Date: 2026-07-17
- Change: `productize-universal-pinn-strategy-system`
- User decision: `Yes`
- Supersedes: case-hierarchy portions of
  `2026-07-17-burgers-qualification.md`

## Approved case relationship

The following are peer scientific validation methods with no primary,
secondary or regression-only hierarchy:

- two-dimensional Poisson;
- classic viscous Burgers;
- two-dimensional lid-driven-cavity incompressible Navier-Stokes;
- two-dimensional heat transfer.

Implementation order, nonlinearity and compute cost do not determine the
scientific rank of a case.

## Approved lid-driven-cavity model

- Steady two-dimensional incompressible Navier-Stokes.
- Unit-square cavity and Reynolds number 100.
- Top lid `u=1,v=0`; all other walls `u=v=0`.
- Zero-mean pressure gauge.
- PINN outputs `u`, `v` and `p`.
- Independent grid-converged CFD test reference with Ghia centerline velocity
  cross-validation.

## Approved metric policy

- Lexicographic primary order: velocity-field `relative_l2`, velocity-vector
  `max_abs`, centerline-velocity RMSE.
- Wall-velocity error is a hard constraint.
- Continuity and momentum residuals, pressure gauge and gauge-invariant
  pressure-gradient error are guardrail or diagnostic evidence.
- Optimization begins only after localizing vector maximum error, centerline
  deviation and high-shear regions.
- At least three seeds are fixed before full execution; rejected seeds remain
  in aggregate evidence and cannot be omitted or rerun based on outcome.

This approval does not waive unit audit, reference convergence, smoke-first
execution, single-intervention isolation, manifest-first idempotency,
provenance, credential isolation or human knowledge-promotion gates.

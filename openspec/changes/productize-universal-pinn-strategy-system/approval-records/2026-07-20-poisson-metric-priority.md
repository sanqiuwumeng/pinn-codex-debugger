# Poisson Metric-Priority Approval

- Date: 2026-07-20
- Decision: `APPROVED`
- Workflow: `poisson-qualification-20260716`
- Approved by: user

The user explicitly replied `Yes` to the following case-local contract:

1. Minimize `relative_l2` as the first lexicographic primary.
2. Minimize `poisson_pde_residual_rms` as the second lexicographic primary.
3. Enforce `poisson_boundary_max_abs <= 1e-6` as a hard constraint.
4. Treat `max_abs`, its `(x,y)` location and `poisson_relative_h1` as
   diagnostics that cannot override the primaries or hard constraint.
5. Replace exactly 12.5% of fixed uniform collocation points with points near
   the diagnosed baseline maximum while holding network, initialization seed,
   optimizer, learning-rate schedule, epoch budget, total collocation count,
   equation, boundary conditions, reference and evaluation grid fixed.

This approval is limited to the declared two-dimensional manufactured Poisson
qualification. It does not establish a default metric policy for other PINNs.

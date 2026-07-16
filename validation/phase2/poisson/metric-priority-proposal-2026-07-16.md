# 2D Poisson Metric-Priority Proposal

Status: `NEEDS_USER_CONFIRMATION`

Case: scalar Poisson equation on the dimensionless unit square with homogeneous
Dirichlet boundary conditions and the manufactured analytic reference
`u(x,y) = sin(pi*x) sin(pi*y)`.

Proposed decision contract:

1. Primary metric: `relative_l2`, minimize against the manufactured analytic
   reference over the complete evaluation grid.
2. Lexicographic tie-breaker: `poisson_pde_residual_rms`, minimize on that same
   complete grid.
3. Hard constraint: `poisson_boundary_max_abs <= 1e-6`, enabled by the hard
   boundary ansatz.
4. Diagnostics only: `max_abs`, its `(x,y)` location, and
   `poisson_relative_h1`. Diagnostics cannot override the primary decision.

The proposed single intervention is to replace 12.5% of fixed uniform
collocation points with points sampled near the baseline's localized maximum.
Network architecture, initialization seed, optimizer, learning-rate schedule,
epoch budget, total collocation count, governing equation, boundary conditions,
reference and evaluation grid remain fixed.

No experiment decision may be emitted until the user confirms this exact
priority and constraint policy.

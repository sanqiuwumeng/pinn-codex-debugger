# Burgers Cross-Domain Qualification Approval

- Date: 2026-07-17
- Change: `productize-universal-pinn-strategy-system`
- User decision: `Yes`

## Approved scientific case

- Replace Poisson as the primary Phase 2 non-thermal scientific qualification
  with the classic viscous Burgers equation.
- Retain the existing Poisson implementation only as a lightweight interface
  and semantic-isolation regression fixture.
- Defer a simple Navier-Stokes/Taylor-Green vortex case to a later multi-channel
  extension so it does not block Phase 2.

## Approved Burgers metric policy

- Lexicographic primaries: `relative_l2 -> max_abs`, both minimized against an
  independently converged numerical test reference.
- The baseline maximum error and high-gradient region must be localized before
  the optimization intervention is selected.
- Initial and boundary errors are hard constraints.
- PDE residual and high-gradient-region error are guardrail/diagnostic evidence.
- At least three seeds are fixed before full execution; rejected seeds remain in
  the aggregate and cannot be rerun or omitted based on their result.

This approval does not waive physical/unit audit, smoke-first execution,
single-intervention isolation, manifest-first idempotency, provenance, rollback,
credential isolation or human knowledge-promotion gates.

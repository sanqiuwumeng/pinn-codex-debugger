# Universal PINN Architecture Approval

- Date: 2026-07-16
- Change: `build-rag-multi-agent-dl-strategy-system`
- User decision: `Yes`

## Confirmed architecture boundary

- The product targets strategy optimization for general PINN models, not one heat-transfer model.
- The universal core contains contracts, orchestration, assurance, generic field diagnostics and provider interfaces only.
- Domain-specific metrics, context extraction and ROI proposals are isolated behind explicitly enabled providers.
- Per-run units, reference evidence, metrics, guardrails, ROI and time windows belong to the case contract.

## Confirmed unit semantics

- The existing PINN-2D validation case uses the proposed SI units.
- The general auditor checks model-internal consistency and conversion chains rather than requiring SI.
- Declared non-SI systems are valid; undeclared or incorrectly converted `m/mm`, `kg/g`, `s/ms` and similar mixtures are blocking findings.

## Confirmed authority and evidence semantics

- The user-provided PDE, BC, IC, geometry and parameters are the physical-model authority.
- Analytic, experimental, numerical and teacher data are separate reference evidence.
- The fine FEM field is reference evidence for the PINN-2D validation case only and is not a universal truth source.

## Confirmed PINN-2D case metric contract

- Aggregation: lexicographic.
- Primary order: `max_abs`, then `RMSE`.
- MAE guardrail: absolute regression no greater than `1.0 K` and relative regression no greater than `10%`; both limits apply.
- ROI, time windows and domain metrics are case-dependent and are not universal defaults.

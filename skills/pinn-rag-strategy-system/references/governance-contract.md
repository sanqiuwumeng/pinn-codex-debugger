# Governance contract

## Layer boundaries

| Layer | Owns | Must not own |
| --- | --- | --- |
| Execution | Explicit process launch, status, cancellation, collection | Scientific decisions or hidden workflow state |
| Orchestration | LangGraph state, interrupts, approvals, stage transitions | Training implementation, implicit globals, secret storage |
| Assurance | Physical audit, metric policy, prediction analysis, validation, replay, knowledge gates | Process launch or unapproved experiment mutation |

Pass data only through declared contracts, immutable artifacts, and explicit service parameters. Do not use global variables, singletons, ambient working directories, or hidden agent memory for functional state.

## Scientific authority

The user-provided physical model is the default authority. A numerical solution such as FEM, FVM, a manufactured solution, or an analytical solution is a validation reference tied to its identity, mesh/grid, parameters, units, and scope. A reference from another physical model cannot silently become truth for the current model.

## Unit audit

The audit checks consistency, not SI conformity. A coherent millimetre-based or gram-based model is acceptable when every equation term, derivative scaling, source term, boundary condition, raw code path, and output channel follows that declaration.

Reject or request confirmation for:

- metre and millimetre values mixed without one explicit conversion;
- kilogram and gram values mixed without one explicit conversion;
- additive equation terms with incompatible dimensions;
- surface and volumetric sources substituted for one another;
- Celsius used directly in an absolute-temperature radiation law;
- missing, duplicated, or ambiguous derivative scaling;
- a declared unit that differs from the unit consumed by the raw implementation path.

## Metric and localization gate

Do not optimize until the user approves the metric policy. A metric contract declares:

- ordered primary metrics or a Pareto policy;
- direction and tolerance for each metric;
- hard constraints;
- guardrails and their units;
- reference identity and compatible evaluation basis;
- output channels and coordinate/time grids.

Prediction analysis precedes the decision. At minimum, retain the `max_abs` value and its location. When the data permit, retain top-k extrema, connected high-error regions, time/channel identity, boundary distance, local PDE residual, gradients, geometry labels, and sampling density.

For a lexicographic policy, evaluate hard constraints and guardrails first. Then compare metrics in the approved order and stop at the first material difference. Never allow a later metric improvement to override an earlier metric regression or a guardrail violation.

The existing temperature example uses both an absolute and relative MAE guardrail. Its `1.0 K` threshold is not valid for velocity, pressure, concentration, or dimensionless fields unless the user defines a corresponding field-specific contract.

## Knowledge gates

RAG evidence is advisory and must preserve provenance. Conflicting claims remain visible and make the result non-decision-safe until resolved.

Wiki publication requires a valid run, evidence integrity, reproducibility, replay, immutable versioning, and scoped approval. Skill promotion is stricter: require two independent validated runs, isolated replay, and explicit Skill-promotion approval. A rejected experiment may enter the Wiki as negative evidence but cannot be represented as a successful optimization.

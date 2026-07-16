## ADDED Requirements

### Requirement: Thermal evidence includes multiple fixed seeds
The existing thermal intervention SHALL be evaluated with at least three predeclared seeds under the unchanged case-specific physical, metric and guardrail contracts.

#### Scenario: One seed fails the guardrail
- **WHEN** other seeds pass but a predeclared seed exceeds either MAE guardrail
- **THEN** the report retains the failure and does not present a universal success based only on aggregate improvement

### Requirement: A real non-thermal PINN completes the governed lifecycle
A classic viscous Burgers PINN with an independently converged numerical test reference SHALL complete audit, metric confirmation, baseline diagnosis, single-intervention smoke, at least three predeclared full seeds, localized analysis, replay and provenance validation. The existing two-dimensional Poisson case SHALL remain a lightweight interface and semantic-isolation regression fixture rather than the primary scientific claim.

#### Scenario: Burgers metric preferences are confirmed
- **WHEN** the case contract is initialized
- **THEN** it declares the user-confirmed lexicographic order `relative_l2 -> max_abs`, reports the maximum-error location before optimization, enforces initial/boundary constraints, treats residual and high-gradient-region error as guardrail/diagnostic evidence, and does not inherit heat-transfer units, regions or MAE thresholds

#### Scenario: One Burgers seed fails a guardrail
- **WHEN** a predeclared seed violates an initial, boundary, residual or high-gradient-region gate
- **THEN** the seed and its localized evidence remain in the report and the system does not rerun or omit it to improve the acceptance rate

### Requirement: Generality claims are bounded by evidence
Release conclusions SHALL distinguish framework validation, case validation, cross-seed evidence and cross-domain evidence.

#### Scenario: Thermal and Burgers evidence is summarized
- **WHEN** release qualification summarizes the results
- **THEN** it may claim the universal architecture works across those declared cases but MUST NOT claim all PINN strategies or PDE families are scientifically optimized

### Requirement: Knowledge promotion requires repeated validated patterns
Wiki and Skill candidates SHALL cite all supporting and contradicting validated runs, and Skill publication SHALL still require explicit human approval.

#### Scenario: A tactic works only for the thermal case
- **WHEN** no compatible non-thermal or repeated evidence supports transfer
- **THEN** the tactic remains case-scoped and cannot be published as a universal PINN Skill

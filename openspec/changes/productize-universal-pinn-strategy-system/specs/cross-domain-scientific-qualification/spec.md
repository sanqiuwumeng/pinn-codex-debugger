## ADDED Requirements

### Requirement: Thermal evidence includes multiple fixed seeds
The existing thermal intervention SHALL be evaluated with at least three predeclared seeds under the unchanged case-specific physical, metric and guardrail contracts.

#### Scenario: One seed fails the guardrail
- **WHEN** other seeds pass but a predeclared seed exceeds either MAE guardrail
- **THEN** the report retains the failure and does not present a universal success based only on aggregate improvement

### Requirement: Active scientific validation cases are peers
Two-dimensional Poisson, classic viscous Burgers and two-dimensional heat transfer SHALL be represented as the current peer scientific validation cases. Implementation order, equation nonlinearity and compute cost MUST NOT create a primary, secondary or regression-only case hierarchy. Existing lid-driven-cavity NS assets SHALL remain an isolated deferred prototype and SHALL NOT block the current release.

#### Scenario: Release evidence is summarized
- **WHEN** a cross-case report compares the three active cases
- **THEN** it reports a case-by-capability evidence matrix and case-local outcomes without assigning a global scientific rank

### Requirement: Every active peer case completes the governed lifecycle
Each active peer case SHALL complete physical and unit audit, user metric confirmation, reference validation, baseline diagnosis, single-intervention smoke, at least three predeclared full seeds, localized analysis, replay and provenance validation without inheriting another case's semantics.

#### Scenario: Burgers metric preferences are confirmed
- **WHEN** the case contract is initialized
- **THEN** it declares the user-confirmed lexicographic order `relative_l2 -> max_abs`, reports the maximum-error location before optimization, enforces initial/boundary constraints, treats residual and high-gradient-region error as guardrail/diagnostic evidence, and does not inherit heat-transfer units, regions or MAE thresholds

#### Scenario: One Burgers seed fails a guardrail
- **WHEN** a predeclared seed violates an initial, boundary, residual or high-gradient-region gate
- **THEN** the seed and its localized evidence remain in the report and the system does not rerun or omit it to improve the acceptance rate

#### Scenario: Poisson is evaluated as scientific evidence
- **WHEN** the Poisson case is qualified
- **THEN** its manufactured reference, elliptic residual, boundary constraints, localized error and multi-seed uncertainty are governed as scientific evidence rather than labeled a lightweight regression fixture

### Requirement: Deferred Navier-Stokes assets remain isolated
The existing steady two-dimensional incompressible lid-driven-cavity reference, worker and domain provider SHALL remain preserved but inactive. They SHALL NOT be imported by default, counted as completed scientific qualification or required by current release gates.

#### Scenario: A current release is qualified
- **WHEN** the active peer-case matrix and engineering gates pass while NS full qualification is still deferred
- **THEN** the release can complete without claiming validated NS optimization

### Requirement: Generality claims are bounded by evidence
Release conclusions SHALL distinguish framework validation, case validation, cross-seed evidence and cross-domain evidence.

#### Scenario: Peer-case evidence is summarized
- **WHEN** release qualification summarizes the results
- **THEN** it may claim the universal architecture works across the three active peer cases but MUST NOT claim validated NS optimization, all PINN strategies or all PDE families are scientifically optimized

### Requirement: Knowledge promotion requires repeated validated patterns
Wiki and Skill candidates SHALL cite all supporting and contradicting validated runs, and Skill publication SHALL still require explicit human approval.

#### Scenario: A tactic works only for the thermal case
- **WHEN** no compatible non-thermal or repeated evidence supports transfer
- **THEN** the tactic remains case-scoped and cannot be published as a universal PINN Skill

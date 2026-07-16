## ADDED Requirements

### Requirement: Metric priorities are confirmed by the user
Before optimization, the system SHALL ask the user to identify the physical-model authority, any available reference evidence, primary metrics, ordering or Pareto policy, guardrails, diagnostic metrics and acceptable regression thresholds. ROI and time windows SHALL be requested only when they are supplied by the user, required by the model/domain provider, or proposed from diagnostic evidence.

#### Scenario: A user has not selected a primary metric
- **WHEN** prediction artifacts exist but the user's metric priority is unknown
- **THEN** the workflow enters `NEEDS_METRIC_PRIORITY` and does not generate an optimization decision

### Requirement: Physical authority and reference evidence are distinct
The user's PDE, BC, IC, geometry, parameters and observation definitions SHALL be the physical authority. Analytic solutions, experiments, numerical solvers and teacher fields SHALL be separately identified reference evidence and MUST be checked for compatibility with that authority.

#### Scenario: FEM is used in one validation case
- **WHEN** a PINN validation case declares a compatible FEM field as its reference evidence
- **THEN** FEM-backed errors are valid for that case but FEM is not promoted to a system-wide truth source

#### Scenario: No reference field exists
- **WHEN** the user supplies a physical model but no aligned truth field
- **THEN** the contract may use residual, BC/IC, conservation, observation or parameter-recovery metrics and MUST NOT fabricate MSE, RMSE or `max_abs` against a nonexistent truth field

### Requirement: The system does not assume one aggregate error is sufficient
The system MUST NOT treat MSE or RMSE as the sole optimization objective unless the user explicitly confirms that policy and no mandatory physical guardrail is violated.

#### Scenario: RMSE improves while a domain guardrail degrades
- **WHEN** a candidate lowers RMSE but violates a user-selected conservation, interface, boundary or other domain metric guardrail
- **THEN** the decision gate rejects the candidate despite the aggregate improvement

### Requirement: Metric contracts distinguish objective roles
The system SHALL distinguish hard constraints, primary objectives, secondary objectives, guardrails and diagnostic-only metrics.

#### Scenario: A candidate is compared with baseline
- **WHEN** all required metrics are available
- **THEN** evaluation first checks hard constraints, then applies the user's primary ordering, then enforces guardrails, and finally uses diagnostics for explanation

### Requirement: Maximum absolute error includes location and context
Every reference-backed `max_abs` result SHALL include its available coordinates, output channel, prediction value, reference value, signed error and model/domain context. Time is required only for time-dependent cases.

#### Scenario: The maximum output error is found
- **WHEN** aligned prediction and reference fields are evaluated
- **THEN** the report records the applicable coordinates and channel together with predicted and reference values rather than returning only one scalar

### Requirement: Localized error structure is analyzed
When supported by the field geometry, the system SHALL compute top-k extreme locations, high-percentile errors, connected high-error regions, slice metrics and location trajectories over applicable independent variables.

#### Scenario: Multiple adjacent points share a high error
- **WHEN** top-k errors form one contiguous physical hotspot
- **THEN** the report identifies the connected region and does not present the points as unrelated failures

#### Scenario: A candidate moves rather than removes the worst error
- **WHEN** candidate `max_abs` decreases at the baseline argmax but a comparable extreme appears elsewhere
- **THEN** the report flags error migration and preserves both locations for decision review

### Requirement: Error locations are joined with model and domain evidence
The system SHALL associate localized prediction errors with available PDE residual, BC/IC status, sampling density, geometry labels and optional domain-provider context.

#### Scenario: A hotspot lies in the phase-change band
- **WHEN** the maximum error occurs where reference temperature is between solidus and liquidus
- **THEN** an explicitly enabled heat-transfer provider labels the phase region and provides local residual and sampling evidence when available; the generic analyzer contains no phase-change assumption

#### Scenario: A hotspot belongs to another PDE family
- **WHEN** a fluid, elasticity, wave or inverse-problem provider supplies domain labels and metrics
- **THEN** the analyzer joins those fields through the same provider interface without importing heat-transfer logic

### Requirement: Baseline and candidate comparisons are aligned
The system SHALL compare prediction fields only after verifying reference identity, units, coordinate system, spatial grid, time grid, masks and output normalization.

#### Scenario: Baseline and candidate use different time slices
- **WHEN** their fields are not aligned to the same physical time coordinates
- **THEN** the metric result is marked invalid until an approved alignment procedure is applied

### Requirement: Optimization decisions require complete diagnostic evidence
The Decision Synthesizer MUST NOT select an intervention without passing physical audit, a confirmed metric contract and a valid model-evaluation report. A prediction-localization report is required only when the selected metrics depend on an aligned reference field.

#### Scenario: Reference-backed aggregate metrics exist but localization failed
- **WHEN** MSE/RMSE were computed but `max_abs` location and ROI analysis are unavailable
- **THEN** the workflow requests diagnostic evidence and does not enter optimization execution

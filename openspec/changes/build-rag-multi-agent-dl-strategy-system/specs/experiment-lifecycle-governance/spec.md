## ADDED Requirements

### Requirement: Experiment completeness is audited before execution
The system SHALL verify source snapshot, dataset identity, environment, random seed, baseline, metric contract, budget, output path, checkpoint policy, expected artifacts and rollback conditions before approving an experiment.

#### Scenario: Baseline provenance is missing
- **WHEN** a candidate is proposed without a traceable baseline run or reference artifact
- **THEN** completeness audit returns `NEEDS_EVIDENCE` and execution is blocked

### Requirement: Each experiment changes one logical point
Every `ExperimentSpec` SHALL declare one logical intervention and an explicit list of controls that remain unchanged.

#### Scenario: A proposal changes sampling, architecture and loss weighting
- **WHEN** three independent interventions appear in one candidate
- **THEN** the assurance layer rejects it or splits it into separately reviewable experiments

### Requirement: Expected outcomes and rollback are declared in advance
Each candidate SHALL define expected primary-metric movement, guardrail limits, falsification conditions and rollback actions before execution.

#### Scenario: Smoke improves a diagnostic metric but violates a guardrail
- **WHEN** the candidate exceeds a predeclared regression threshold
- **THEN** the run is not promoted and the recorded rollback policy is proposed for approval

### Requirement: Smoke validation precedes full training
The system SHALL run an approved smoke or read-only validation stage before requesting permission for full or expensive training.

#### Scenario: A new optimization strategy is selected
- **WHEN** no validated smoke run exists for its exact intervention and controls
- **THEN** the graph cannot transition directly to `FULL_RUNNING`

### Requirement: Full runs require separate approval
Passing smoke validation SHALL NOT itself authorize full training; the system SHALL persist estimated cost, duration, resources and smoke evidence and wait for explicit approval.

#### Scenario: Smoke validation passes
- **WHEN** the selected strategy meets smoke acceptance criteria
- **THEN** the graph enters `NEEDS_FULL_RUN_APPROVAL` instead of starting full training automatically

### Requirement: Execution is manifest-first and idempotent
The runner SHALL persist a `RunManifest` and idempotency key before launching external work and SHALL detect repeated launch requests.

#### Scenario: A workflow resumes after a launch response is lost
- **WHEN** the same idempotency key is submitted again
- **THEN** the runner returns the existing run reference rather than starting a duplicate job

### Requirement: Monitoring is event-driven
The system SHALL collect structured run, metric, checkpoint, resource, NaN, OOM, stalled-log and artifact events, and SHALL invoke interpretive Agents only for declared anomalies or milestones.

#### Scenario: Training logs continue normally
- **WHEN** no threshold, health or milestone rule is triggered
- **THEN** deterministic monitoring records events without repeatedly sending the complete log to an LLM

### Requirement: Result validity is independent from process completion
A process exit code of zero SHALL NOT be sufficient to mark a result valid; required metrics, artifacts, provenance, alignment and physical checks SHALL also pass.

#### Scenario: Training exits successfully but the reference comparison file is absent
- **WHEN** the process finishes with code zero and a required artifact is missing
- **THEN** the run status becomes `RESULT_INVALID` and it cannot enter knowledge curation

### Requirement: Recovery preserves evidence and avoids destructive cleanup
Failure recovery SHALL retain logs, manifests, checkpoints and partial artifacts and MUST NOT delete or overwrite user data automatically.

#### Scenario: A run fails with GPU OOM
- **WHEN** the monitor records the failure
- **THEN** the system preserves evidence, proposes at most one next intervention and waits for approval before changing the experiment

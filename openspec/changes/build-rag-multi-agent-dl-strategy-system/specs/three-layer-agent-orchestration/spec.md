## ADDED Requirements

### Requirement: The system enforces three physically isolated layers
The system SHALL separate execution, orchestration and assurance functions into independently testable modules with explicit versioned request and response objects.

#### Scenario: An orchestration node requests experiment execution
- **WHEN** the orchestration layer selects an approved `ExperimentSpec`
- **THEN** it passes that object to the execution adapter without importing runner internals or using implicit shared state

#### Scenario: An assurance gate rejects a transition
- **WHEN** any mandatory assurance report has a non-passing status
- **THEN** the graph prevents the downstream execution transition and persists the rejection reason

### Requirement: LangGraph is the authoritative workflow coordinator
The system SHALL express lifecycle states, branches, interrupts, retries and completion conditions as explicit LangGraph nodes and edges rather than a free-form multi-Agent conversation.

#### Scenario: A unit ambiguity requires user input
- **WHEN** physical audit returns `NEEDS_UNIT_CONFIRMATION`
- **THEN** the graph enters a persisted interrupt and resumes from that state after the user responds

#### Scenario: A completed read-only node is resumed after failure
- **WHEN** a later graph node fails and execution is resumed from a checkpoint
- **THEN** previously completed idempotent nodes are not needlessly repeated

### Requirement: Workflow state contains references rather than large artifacts
The system SHALL keep model weights, arrays, figures and complete logs outside graph state and SHALL store only identifiers, small structured values and artifact references in `WorkflowState`.

#### Scenario: Prediction fields are produced
- **WHEN** an evaluator generates a large aligned prediction/reference field
- **THEN** the field is saved to an artifact store and graph state receives an immutable `ArtifactRef`

### Requirement: Functional data has no implicit transport path
The system MUST NOT pass business data through global mutable variables, singletons, process working-directory assumptions or hidden Agent memory.

#### Scenario: Two workflows run concurrently
- **WHEN** separate workflow IDs execute the same specialist node
- **THEN** each node reads only its declared inputs and cannot observe the other workflow's functional state

### Requirement: Specialist subgraphs declare persistence semantics
Each specialist subgraph SHALL explicitly declare whether it is per-invocation, per-thread or stateless, and the MVP SHALL default independent specialist tasks to per-invocation persistence.

#### Scenario: The same retrieval specialist is called for two candidates
- **WHEN** two candidate strategies request retrieval independently
- **THEN** each invocation receives its own explicit context and does not accumulate unreviewed memory from the other candidate

### Requirement: High-impact actions require persisted approval
The system SHALL use human-interrupt gates for modifying existing files, installing dependencies, starting full runs, publishing models, promoting Wiki entries and publishing Skills.

#### Scenario: A full training run is proposed
- **WHEN** smoke validation passes and a full run is requested
- **THEN** the graph persists the proposed budget and waits for an explicit approval record before starting the run

### Requirement: Implementation remains gated by explicit architecture approval
This OpenSpec change MUST NOT be implemented until the user explicitly replies `Yes` for this architecture and the dependency/environment plan is recorded.

#### Scenario: Planning documents are complete but implementation approval is absent
- **WHEN** the RFC and tasks are ready for review without a fresh explicit `Yes`
- **THEN** work stops before creating architectural runtime modules or installing packages

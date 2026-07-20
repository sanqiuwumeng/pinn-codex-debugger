## ADDED Requirements

### Requirement: The CLI is a thin application-service client
`pinn-strategy` SHALL expose audit, plan, smoke, full, status, replay and RAG operations without duplicating workflow transitions, physical calculations or metric decisions.

#### Scenario: A user requests a full run
- **WHEN** `pinn-strategy full` is invoked for a workflow without an applicable persisted approval
- **THEN** the CLI reports a needs-approval outcome and does not launch a backend

### Requirement: CLI inputs are explicit and outputs are stable
The CLI SHALL resolve all file paths to absolute paths, support versioned JSON output and use documented exit codes for success, needs-input, gate-rejected, run-failed and internal-error outcomes.

#### Scenario: Automation requests JSON
- **WHEN** any supported command is invoked with `--json`
- **THEN** stdout contains one schema-versioned result object and diagnostics are separated without corrupting the JSON stream

### Requirement: CLI commands preserve workflow interrupts and replay
The CLI SHALL surface persisted `NEEDS_*` states and SHALL resume through application services rather than reconstructing hidden conversational state.

#### Scenario: Unit confirmation is required
- **WHEN** audit reaches `NEEDS_UNIT_CONFIRMATION`
- **THEN** the CLI returns the exact unresolved records and a later invocation can resume the same workflow ID

### Requirement: CLI errors do not leak secrets
All CLI output and persisted diagnostics SHALL redact credentials and direct remote connection secrets.

#### Scenario: An SSH command fails
- **WHEN** the underlying transport includes sensitive runtime arguments
- **THEN** the user receives a sanitized failure and the raw secret-bearing command is not written to logs

### Requirement: CLI exposes the complete operational chain
`pinn-strategy` SHALL expose project adaptation, read-only MCP diagnosis and deterministic post-run evaluation in addition to existing audit, plan, execution, status and RAG operations. Each command SHALL remain a thin client over an injected application service.

#### Scenario: A user onboards an existing PINN project
- **WHEN** `pinn-strategy adapt` receives a valid project manifest and a new output path
- **THEN** it verifies the declared project files, emits an `OperatorCase` with a deterministic source snapshot, and reports unresolved user-governed fields without guessing them

#### Scenario: A user requests quick fault retrieval
- **WHEN** `pinn-strategy diagnose` receives an observable symptom and an explicit MCP runtime profile
- **THEN** it calls the isolated read-only MCP provider and returns source hash plus line-range evidence without mutating workflow state

#### Scenario: A completed run is evaluated
- **WHEN** `pinn-strategy evaluate` receives an explicit field-evaluation contract
- **THEN** it checks field identity and alignment, reports `max_abs` location before decision, applies the user-confirmed metric order and writes immutable evidence artifacts

#### Scenario: Completed run artifacts are collected
- **WHEN** `pinn-strategy collect` is invoked for a reconciled completed run and a new explicit destination
- **THEN** it calls the production backend collection contract, verifies source and destination manifests, and refuses overwrite

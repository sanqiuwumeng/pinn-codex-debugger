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

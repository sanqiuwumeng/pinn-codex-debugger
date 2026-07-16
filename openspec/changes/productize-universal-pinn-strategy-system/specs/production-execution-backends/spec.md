## ADDED Requirements

### Requirement: Execution backends implement the full run lifecycle
Each production backend SHALL implement explicit prepare, launch, reconcile, cancel and collect operations using versioned request and response contracts.

#### Scenario: An orchestration node launches a prepared run
- **WHEN** a valid manifest and persisted approval reach the execution service
- **THEN** the backend launches only the prepared command and returns a durable backend reference

#### Scenario: A launch response is lost
- **WHEN** the registry records an uncertain launch outcome
- **THEN** the system reconciles the backend reference and MUST NOT retry launch until non-execution is proven

### Requirement: Local execution is durable and path-explicit
The local backend SHALL use absolute paths, argument arrays, an environment allowlist, durable status/log files and process creation identity.

#### Scenario: An operating-system PID is reused
- **WHEN** the stored PID exists but its creation identity differs
- **THEN** reconciliation rejects it as the governed process and uses persisted status and artifacts to determine the run outcome

### Requirement: AutoDL execution survives transport disconnects
The AutoDL backend SHALL stage content by hash, launch through a durable remote wrapper and reconcile from remote process, heartbeat, status, log and artifact evidence.

#### Scenario: SSH disconnects while training continues
- **WHEN** the transport fails after the remote launcher records the process
- **THEN** the run remains reconcilable and a replay does not create a second training process

### Requirement: Cancellation and artifact collection are governed
Cancellation SHALL require an applicable approval, and collection SHALL verify remote and local manifests before artifacts become authoritative.

#### Scenario: Result transfer is interrupted
- **WHEN** only part of the remote archive arrives
- **THEN** the partial copy is retained as non-authoritative evidence and is not promoted into the artifact store

### Requirement: Backend data flow is physically isolated
Backends MUST receive all functional data explicitly and MUST NOT read global credentials, mutable singletons, implicit working directories or hidden Agent memory.

#### Scenario: Two workflows use the same backend implementation
- **WHEN** they execute concurrently
- **THEN** each uses only its own profile, run root, manifest, approval and artifact collection specification

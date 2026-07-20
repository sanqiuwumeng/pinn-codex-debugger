## ADDED Requirements

### Requirement: Remote qualification uses an exact source snapshot
The AutoDL workspace SHALL be staged from one committed Git archive and SHALL record the local commit and archive SHA-256 before execution.

#### Scenario: Remote archive hash differs
- **WHEN** the uploaded archive does not match the local SHA-256
- **THEN** extraction and formal execution are blocked

### Requirement: Qwen and PINN runtimes remain physically isolated
Embedding/reranking and PINN training SHALL execute in separate approved environments and communicate only through explicit serialized contracts and artifacts.

#### Scenario: Runtime readiness is checked
- **WHEN** the full chain is about to start
- **THEN** both environments pass dependency checks and the Qwen environment completes a real GPU kernel before model loading

### Requirement: Full-chain validation includes real retrieval and real PINN evidence
The qualification SHALL use the pinned Qwen3 embedding and reranking providers to retrieve formal Wiki evidence and SHALL run one governed PINN audit, smoke/full execution, collection, localized analysis, metric decision and replay.

#### Scenario: The published Wiki is absent after reranking
- **WHEN** the formal query completes but the approved Wiki is not returned with matching source and model revisions
- **THEN** the end-to-end qualification fails even if the PINN run succeeds

#### Scenario: The PINN optimization is rejected
- **WHEN** the independent run fails its approved case metric contract
- **THEN** the chain may prove governance completeness but MUST retain the rejection and MUST NOT claim scientific improvement

### Requirement: RAG evidence is advisory to deterministic science
Retrieved Wiki evidence MAY inform the proposed experiment but SHALL NOT replace the user-authoritative physics, reference validation, measured fields or approved metric decision.

#### Scenario: Retrieved guidance conflicts with measured results
- **WHEN** RAG suggests an intervention but the measured metric contract rejects it
- **THEN** the deterministic decision wins and the contradiction remains visible

### Requirement: Remote evidence is transferred only after verified completion
The system SHALL require a zero exit marker, final log marker, expected artifacts, file count, size and hashes before downloading the result once.

#### Scenario: A remote job is still running
- **WHEN** no successful status marker exists
- **THEN** the large result directory is not transferred

## ADDED Requirements

### Requirement: Qwen3 models run outside orchestration and training environments
The production embedding and reranking providers SHALL communicate with an isolated model process through a versioned, explicitly injected transport.

#### Scenario: The orchestrator embeds a query
- **WHEN** `Qwen3EmbeddingProvider` receives an embedding request
- **THEN** it sends a bounded structured request and validates the returned request ID, model revision, vector count, dimensions and finite values

### Requirement: Production providers use immutable accepted revisions
The embedding provider SHALL use `Qwen/Qwen3-Embedding-8B` revision `1d8ad4ca9b3dd8059ad90a75d4983776a23d44af`, and the reranker SHALL use `Qwen/Qwen3-Reranker-4B` revision `22e683669bc0f0bd69640a1354a6d0aebcfeede5` unless a later revision passes a separate approval and qualification change.

#### Scenario: A local cache points to another revision
- **WHEN** model startup resolves a revision different from the approved immutable value
- **THEN** startup fails before serving any embedding or reranking response

### Requirement: Reranking preserves evidence conflicts
The retrieval pipeline SHALL rerank at least six ordinary candidates and at least ten conflict/all-evidence candidates and SHALL preserve all provenance and claim metadata required by deterministic conflict detection.

#### Scenario: Two high-quality sources disagree
- **WHEN** dense retrieval finds both conflict documents
- **THEN** reranking cannot silently drop the contradiction and the final response remains decision-unsafe until the conflict is resolved

### Requirement: Vector indexes are versioned derived data
Collection identity SHALL include model revision, chunk schema, metadata schema and source manifest identity, and activation SHALL occur only after validation canaries pass.

#### Scenario: A rebuild fails its provenance canary
- **WHEN** a newly built collection contains missing or mismatched source references
- **THEN** the active collection remains unchanged and the failed build is recorded without deleting source facts

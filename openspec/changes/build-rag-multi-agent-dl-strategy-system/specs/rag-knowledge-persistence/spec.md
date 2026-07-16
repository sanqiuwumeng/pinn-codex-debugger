## ADDED Requirements

### Requirement: Existing deterministic retrieval remains an isolated provider
The system SHALL reuse the current `pinn-hybrid-rag` capability through an explicit adapter and SHALL NOT add workflow execution or persistence side effects to the retrieval server.

#### Scenario: The graph requests handbook evidence
- **WHEN** a Strategy Planner submits a retrieval request
- **THEN** the adapter returns structured evidence and the MCP service remains read-only

### Requirement: Vector retrieval supplements rather than replaces deterministic evidence
The retrieval pipeline SHALL combine deterministic symptom routing and anchors with approved sparse and dense retrieval, metadata filtering, fusion, conflict checking and reranking.

#### Scenario: A query uses an unseen cross-language paraphrase
- **WHEN** deterministic anchors have weak recall
- **THEN** vector retrieval may add candidates while every accepted result still passes provenance validation

### Requirement: Retrieval applies metadata scope before ranking
The system SHALL filter by project, source type, validation state, model family, framework and applicable version before semantic ranking whenever those fields are available.

#### Scenario: Similar reports exist for unrelated projects
- **WHEN** a PINN experiment queries prior optimization evidence
- **THEN** reports outside the declared project/model scope are excluded or explicitly marked as cross-project evidence

### Requirement: Every indexed item has rebuildable provenance
Each indexed chunk SHALL record source URI, source hash, line or artifact range, repository commit, validation status and applicable experiment identifiers.

#### Scenario: A retrieved Wiki paragraph supports a decision
- **WHEN** the paragraph appears in ranked evidence
- **THEN** the response includes enough metadata to locate the exact approved source version

### Requirement: The vector database is a derived index
The vector store MUST NOT be the sole repository for experiment facts, Wiki source or Skill source, and the complete index SHALL be rebuildable from authoritative stores.

#### Scenario: The vector collection is deleted
- **WHEN** an administrator rebuilds the index
- **THEN** no source experiment, artifact, Wiki document or Skill file is lost

### Requirement: Experiment records use explicit storage ownership
The system SHALL assign workflow checkpoints, run metadata, large artifacts, retrieval indexes, audit events and versioned knowledge to separate declared stores.

#### Scenario: A model checkpoint is recorded
- **WHEN** training writes a checkpoint
- **THEN** the binary is stored as an artifact, run metadata stores its reference, and graph state stores only the run or artifact identifier

### Requirement: Wiki entries require validated evidence
Only results with passing metric, artifact, physical and reproducibility reports SHALL produce publishable Wiki candidates, and publication SHALL require human approval.

#### Scenario: A smoke run completes but is not a scientific validation
- **WHEN** smoke proves only workflow correctness
- **THEN** its Wiki candidate is labelled as smoke evidence and cannot claim model effectiveness

### Requirement: Knowledge versions preserve supersession and invalidation
Wiki and Skill records SHALL retain version, source references, validity status and `supersedes` relationships instead of rewriting historical conclusions in place.

#### Scenario: A repeated experiment overturns an earlier conclusion
- **WHEN** the new result passes validation and is approved
- **THEN** it creates a new knowledge version that supersedes but does not delete the earlier record

### Requirement: Skills follow a governed promotion pipeline
The system SHALL generate `SkillCandidate` records only from repeated validated patterns and SHALL require isolated replay, baseline comparison and explicit human review before publication.

#### Scenario: One successful experiment suggests a reusable tactic
- **WHEN** the curator identifies the tactic after a single run
- **THEN** it remains a candidate and is not published as a reusable Skill

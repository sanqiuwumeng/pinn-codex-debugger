## ADDED Requirements

### Requirement: Formal Wiki publication requires exact human approval
The system SHALL create a formally published Wiki entry only from a validated Wiki candidate and an approved `KNOWLEDGE_PROMOTION` record whose scope exactly names that candidate.

#### Scenario: Approval scope names another candidate
- **WHEN** a valid candidate is submitted with an approval scoped to another Wiki candidate
- **THEN** publication is rejected and no authoritative version directory is created

### Requirement: Published Wiki versions are append-only and atomic
Each formal Wiki version SHALL be committed as one immutable version directory containing the publication contract, human-readable entry, RAG index document and SHA-256 manifest.

#### Scenario: A version path already contains different content
- **WHEN** publication targets an existing Wiki ID and version with a different payload
- **THEN** the store reports a conflict and does not overwrite any file

#### Scenario: The identical publication is replayed
- **WHEN** every expected file and hash matches the existing version
- **THEN** the store returns a verified idempotent receipt without rewriting the version

### Requirement: RAG content derives from the formal publication
The Wiki RAG document SHALL derive its text, validity, effective time, version, source hash, metadata and claims from the same immutable published entry.

#### Scenario: The vector index is rebuilt
- **WHEN** the authoritative Wiki directory is indexed again
- **THEN** the rebuilt chunk preserves the published Wiki identity, approval status and source provenance

### Requirement: Wiki and Skill promotion remain separate
Formal Wiki publication SHALL NOT promote a Skill or satisfy the independent Skill replay requirement.

#### Scenario: The Wiki publication succeeds
- **WHEN** the approved Wiki is committed
- **THEN** the related Skill remains an unpromoted candidate

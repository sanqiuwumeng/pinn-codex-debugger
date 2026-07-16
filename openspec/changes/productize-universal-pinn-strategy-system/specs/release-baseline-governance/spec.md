## ADDED Requirements

### Requirement: A selective Git baseline precedes product feature edits
The system SHALL classify the complete uncommitted workspace and SHALL establish a tested source-and-evidence baseline before modifying production runtime interfaces.

#### Scenario: Large generated experiment artifacts are present
- **WHEN** baseline preparation finds model weights, arrays, databases, full logs or generated workspaces
- **THEN** it preserves them outside Git, records authoritative hashes and references, and does not delete them

#### Scenario: Source and governed reports are ready
- **WHEN** classification, backup, regression and credential checks pass
- **THEN** source, tests, OpenSpec, small manifests and governed reports may enter one traceable baseline commit

### Requirement: Existing files are backed up before modification
Every existing file modified by this change SHALL first have a dated backup whose filename follows `original_filename_backup_YYYY-MM-DD` inside a traceable backup directory.

#### Scenario: Ignore rules require editing
- **WHEN** `.gitignore` is selected for modification
- **THEN** its original content is copied to a compliant dated backup before the patch is applied

### Requirement: Secrets never enter governed artifacts
Repository content, manifests, workflow checkpoints, logs, Wiki and Skill records MUST NOT contain passwords, private keys or directly usable remote connection strings.

#### Scenario: A remote profile is persisted
- **WHEN** the AutoDL backend records provenance
- **THEN** it stores only a profile identifier and host/key fingerprints and obtains secrets at runtime

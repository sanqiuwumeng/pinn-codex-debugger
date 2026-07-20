## ADDED Requirements

### Requirement: Project onboarding is manifest-driven and evidence-preserving
The system SHALL onboard an existing PINN project from an explicit adapter manifest containing an absolute project root, declared source paths and user-governed contract inputs. It SHALL compute a deterministic source snapshot and SHALL NOT infer PDE semantics, units, reference authority or metric priority from names alone.

#### Scenario: Required physics are ambiguous
- **WHEN** declared inputs are insufficient to construct a complete physical model or metric contract
- **THEN** adaptation returns structured unresolved records and does not launch training or invent defaults

### Requirement: Project scans are confined and deterministic
Every declared source path SHALL resolve inside the explicit project root, be a regular file, and contribute its relative path, byte count and SHA-256 to a sorted snapshot manifest.

#### Scenario: A path escapes the project root
- **WHEN** an include path resolves outside the declared project root
- **THEN** adaptation rejects the manifest before writing an operator case

### Requirement: MCP diagnosis remains a read-only upstream evidence source
The project loop SHALL access the existing PINN handbook MCP through an explicitly configured stdio process and verify the selected tool's read-only and non-destructive annotations before use.

#### Scenario: MCP safety annotations are missing
- **WHEN** the MCP tool is not declared read-only and non-destructive
- **THEN** diagnosis fails closed and no evidence is attached to the workflow

### Requirement: Post-run evaluation is artifact-contract driven
The evaluator SHALL load baseline, candidate and reference fields only from explicit field artifact descriptors, verify hashes, shapes, axes, coordinates, reference identity, units and normalization, and localize maximum error before applying metric decisions.

#### Scenario: Candidate coordinates differ from the reference
- **WHEN** any required coordinate array is not exactly aligned
- **THEN** the evaluation is `RESULT_INVALID`, no optimization acceptance is produced and no Wiki/Skill candidate is generated

### Requirement: Evidence persistence does not imply knowledge publication
Comparison and decision outputs SHALL be written to a no-overwrite artifact store. A knowledge candidate MAY be emitted only from valid evidence, and publication SHALL remain a separate explicit human action.

#### Scenario: A candidate strategy is accepted once
- **WHEN** one governed evaluation accepts a candidate
- **THEN** the system may create a case-scoped Wiki candidate but cannot publish a reusable Skill automatically

# pinn-debug-skill-baseline Specification

## Purpose
TBD - created by archiving change build-pinn-debug-skill-baseline. Update Purpose after archive.
## Requirements
### Requirement: Self-Contained Codex Skill
The implementation SHALL provide a repo-owned Codex skill folder that can later be installed without relying on files outside the skill directory.

#### Scenario: Skill folder is portable
- **WHEN** the skill directory is inspected after implementation
- **THEN** it contains `SKILL.md`, `agents/openai.yaml`, required Markdown references, and evaluation fixtures inside the skill directory

### Requirement: Dependency-Free Baseline
The implementation MUST NOT add MCP servers, databases, embeddings, external API calls, package installations, or conda environment modifications.

#### Scenario: Baseline remains lightweight
- **WHEN** the skill baseline is implemented and validated
- **THEN** no new runtime dependency, background service, or conda package change is required

### Requirement: Progressive Handbook Disclosure
The skill SHALL direct Codex to load a compact routing index first and search the full Markdown handbook only for the symptom, check, or module relevant to the current request.

#### Scenario: Focused handbook lookup
- **WHEN** a user asks why a PINN boundary condition is not satisfied
- **THEN** Codex reads the routing guidance and searches the handbook for boundary-related evidence and checks instead of loading unrelated module chapters

### Requirement: Symptom-First Diagnosis
The skill SHALL begin diagnosis from an observable symptom and supporting evidence before recommending an enhancement module.

#### Scenario: Late-time divergence is diagnosed before module selection
- **WHEN** a user reports that initial conditions are satisfied but later time intervals diverge
- **THEN** Codex identifies the late-time symptom, requests or inspects relevant time-segment evidence, and completes basic checks before recommending a temporal module

### Requirement: Mandatory Basic Checks
The skill MUST require checks for equation correctness, variables and dimensions, automatic differentiation, boundary and initial-condition definitions, scaling, sampling, loss components, optimizer settings, precision, and logging when relevant to the reported symptom.

#### Scenario: Premature architecture change is blocked
- **WHEN** a user asks to add a deeper network because total loss is not decreasing
- **THEN** Codex prioritizes basic implementation, scaling, loss, sampling, and optimizer checks before proposing a network architecture change

### Requirement: Single-Change Recommendation
The skill SHALL recommend at most one logical intervention for the next experiment unless the user explicitly asks for a broader comparative plan.

#### Scenario: Local residual hotspot receives one next action
- **WHEN** a residual heatmap shows a localized hotspot and basic sampling checks are complete
- **THEN** Codex recommends one sampling-focused intervention and does not stack unrelated architecture modules into the same next experiment

### Requirement: Validation and Rollback Contract
Each recommended intervention SHALL name an expected metric improvement and a rollback condition.

#### Scenario: Hard constraint recommendation is falsifiable
- **WHEN** Codex recommends a hard boundary constraint after boundary-expression checks pass
- **THEN** the response names the boundary-error metric expected to improve and states when to revert to the baseline

### Requirement: Source-Grounded Response
Diagnostic guidance SHALL cite the relevant handbook reference file and heading or search anchor.

#### Scenario: Module guidance is traceable
- **WHEN** Codex recommends investigating Causal PINN for late-time divergence
- **THEN** the response identifies the relevant handbook heading or search anchor so the user can verify the basis of the recommendation

### Requirement: Handbook Provenance
The skill-local handbook copy MUST be byte-identical to the repository-root Markdown source at implementation time, and the implementation summary SHALL record its SHA256.

#### Scenario: Reference copy is verified
- **WHEN** implementation verification runs
- **THEN** the source handbook and packaged handbook copy produce the same SHA256 hash

### Requirement: Repeatable Baseline Evaluation
The implementation SHALL include reusable evaluation fixtures and a scoring rubric that can be applied unchanged to later MCP and hybrid-RAG branches.

#### Scenario: Evaluation covers major symptom classes
- **WHEN** the evaluation fixtures are reviewed
- **THEN** they include boundary-condition failure, late-time divergence, local residual hotspots, high-frequency smoothing, inverse-parameter drift, conservation drift, high-order PDE instability, repeated parametric solves, and an underspecified symptom

### Requirement: Underspecified Cases Avoid Overdiagnosis
The skill SHALL request missing evidence or describe the next observation needed when the user's symptom is too vague to justify a module recommendation.

#### Scenario: Vague failure report is handled conservatively
- **WHEN** a user only says that the PINN result is bad
- **THEN** Codex asks for concrete observable evidence and does not recommend an enhancement module

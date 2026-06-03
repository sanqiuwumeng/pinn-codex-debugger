# pinn-debug-blind-evaluation Specification

## Purpose
TBD - created by archiving change advance-pinn-debugger-experiments. Update Purpose after archive.
## Requirements
### Requirement: Blind evaluation covers nine symptom families
The evaluation suite SHALL include isolated cases for boundary failure, late-time divergence, local residual hotspots, high-frequency smoothing, inverse-parameter drift, conservation drift, high-order PDE instability, repeated parametric solves, and underspecified failure.

#### Scenario: Blind suite coverage is reviewed
- **WHEN** the canonical blind suite manifest is inspected
- **THEN** each required symptom family has at least one blind prompt

### Requirement: Blind prompts do not leak expected behavior
Blind prompts MUST NOT name the Skill, retrieval implementation, expected module, handbook anchor, or acceptance criteria.

#### Scenario: An isolated thread receives a blind prompt
- **WHEN** a blind evaluation thread is started
- **THEN** the thread receives only the user-style symptom prompt and no hidden expected answer

### Requirement: Raw blind-test evidence is preserved
Each blind-test run SHALL preserve the exact prompt, thread identifier, raw response, scoring notes, and suite summary under `validation/blind-tests/<YYYY-MM-DD>_<suite-name>/`.

#### Scenario: A blind run is scored
- **WHEN** a response is evaluated
- **THEN** the raw response and its scoring record can be audited from the archived evidence

### Requirement: Branch comparisons use the same benchmark
The `skill-only`, `rules-mcp`, and `hybrid-rag` experiments SHALL reuse the same frozen blind prompts and scoring rubric.

#### Scenario: A richer retrieval branch is evaluated
- **WHEN** the branch comparison is run
- **THEN** prompt content and rubric criteria match the frozen baseline benchmark

### Requirement: Diagnostic discipline remains measurable
The evaluation SHALL record symptom classification, relevant basic checks, single-change discipline, metric and rollback quality, handbook traceability, retrieval misses, synonym-expansion needs, module stacking, and response-concision deviations.

#### Scenario: Evaluation summary is generated
- **WHEN** a branch completes the blind suite
- **THEN** the summary reports diagnosis-quality and retrieval-behavior measures for comparison

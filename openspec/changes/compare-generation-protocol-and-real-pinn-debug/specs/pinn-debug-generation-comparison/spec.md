## ADDED Requirements

### Requirement: All schemes use one answer-generation contract
The comparison SHALL evaluate `skill-only`, `rules-mcp`, and `hybrid-rag` through a shared answer-generation protocol before comparing final diagnostic answer quality.

#### Scenario: A frozen blind prompt is evaluated
- **WHEN** any of the three schemes receives a blind prompt
- **THEN** its final answer follows the same required fields, one-change discipline, metric expectation, rollback condition, and handbook-citation requirement

### Requirement: Retrieval metrics and answer scores remain separate
The comparison SHALL NOT treat family routing, top-heading accuracy, or retrieval recall as equivalent to end-to-end blind answer score.

#### Scenario: Results are summarized
- **WHEN** the report compares `skill-only`, `rules-mcp`, and `hybrid-rag`
- **THEN** it reports retrieval metrics separately from natural-language answer scores

### Requirement: Frozen prompts and rubric are reused
The comparison SHALL reuse the canonical nine-family blind prompts and scoring rubric unless a deviation is explicitly recorded.

#### Scenario: Round 1 starts
- **WHEN** the evaluator launches the answer-generation comparison
- **THEN** each scheme receives equivalent blind prompt content and is scored with the same rubric

### Requirement: Raw answer evidence is archived
Every generated answer SHALL preserve its exact prompt, scheme context, retrieval evidence if any, raw response, scoring note, and run identifier.

#### Scenario: An answer is scored
- **WHEN** a score is assigned
- **THEN** an auditor can inspect the raw answer and the evidence used to assign the score

# hybrid-rag-retrieval Specification

## Purpose
TBD - created by archiving change advance-pinn-debugger-experiments. Update Purpose after archive.
## Requirements
### Requirement: Architectural implementation requires explicit approval
The `hybrid-rag` experiment MUST NOT be implemented until the user explicitly replies `Yes` to approve the architectural change and any required dependency plan.

#### Scenario: Hybrid RAG implementation is requested without approval
- **WHEN** the project reaches the `hybrid-rag` implementation stage without an explicit `Yes`
- **THEN** implementation pauses before creating or modifying architectural files

### Requirement: Hybrid retrieval is physically isolated
The `hybrid-rag` experiment SHALL place its functional modules inside the existing `exp/hybrid-rag` worktree and SHALL exchange data only through explicit request and response objects.

#### Scenario: Semantic retrieval request is processed
- **WHEN** a query and optional symptom metadata are submitted
- **THEN** the retrieval component returns explicit ranked results without global variables, singletons, or implicit dependencies

### Requirement: Paraphrased symptoms are retrievable
The hybrid retrieval component SHALL retrieve relevant handbook sections for paraphrased symptom descriptions that do not contain the handbook's exact keyword anchors.

#### Scenario: Query uses an unseen paraphrase
- **WHEN** a user describes a known symptom without using the canonical handbook phrase
- **THEN** the relevant symptom family and handbook section appear in the ranked results

### Requirement: Handbook sections are ranked
The hybrid retrieval component SHALL return ranked handbook sections with scores, source anchors, and source handbook provenance.

#### Scenario: Multiple sections contain a common module name
- **WHEN** a query matches several handbook locations
- **THEN** the response ranks the most relevant section ahead of generic mentions and preserves verifiable source anchors

### Requirement: Semantic dependencies are approved and recorded
Any embedding model, indexing library, storage format, or conda environment change MUST be proposed explicitly, approved before installation, and recorded with versions and index inputs.

#### Scenario: Semantic backend is selected
- **WHEN** implementation requires a new local package or model
- **THEN** installation waits for approval and the accepted dependency plan is recorded

### Requirement: Hybrid RAG is compared against the frozen benchmark
The `hybrid-rag` experiment SHALL replay the canonical blind suite and paraphrase variants, then report its results against both `skill-only` and `rules-mcp`.

#### Scenario: Hybrid RAG evaluation completes
- **WHEN** semantic retrieval validation finishes
- **THEN** its report uses the frozen rubric and records recall, ranking, traceability, and response-quality differences

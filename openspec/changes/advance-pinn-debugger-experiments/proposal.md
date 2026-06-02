## Why

The `skill-only` PINN debugging baseline is implemented and installed, but its repository record still reflects the pre-installation state and its independent blind testing covers only boundary-focused cases. Before comparing richer retrieval approaches, the project needs a reproducible baseline release, broader blind evaluation, and two isolated follow-up experiments that can be judged against the same evidence.

## What Changes

- Close out the `skill-only` baseline: back up documents before revision, record installation and blind-test results, decide where blind-test evidence is archived, re-run validation, and prepare an intentional commit.
- Expand isolated blind testing so all nine baseline symptom families are represented and scored with the same rubric.
- Build a `rules-mcp` experiment in its existing worktree for structured symptom records and deterministic evidence extraction.
- Build a `hybrid-rag` experiment in its existing worktree for paraphrase retrieval and handbook-section ranking.
- Keep the original handbook unchanged and reuse the same fixtures, rubric, and provenance checks across all three comparison branches.
- Require a separate explicit user reply of `Yes` before implementing either architectural experiment.

## Capabilities

### New Capabilities

- `skill-only-baseline-release`: Defines the repository closeout, provenance, installation record, and commit-readiness requirements for the text-only baseline.
- `pinn-debug-blind-evaluation`: Defines isolated, repeatable blind testing across the nine symptom families and comparable result recording.
- `rules-mcp-retrieval`: Defines the structured symptom-record and deterministic evidence-extraction experiment in the `rules-mcp` worktree.
- `hybrid-rag-retrieval`: Defines the semantic retrieval and handbook-section ranking experiment in the `hybrid-rag` worktree.

### Modified Capabilities

- None.

## Impact

- Affected worktrees: `exp/skill-only`, then `exp/rules-mcp`, then `exp/hybrid-rag`; no new worktrees are created.
- Affected artifacts: repo-owned skills, evaluation fixtures, blind-test records, OpenSpec documents, and later experiment-specific MCP or retrieval components.
- Data safety: preserve the source handbook byte-for-byte, back up each existing file before revision using the required date suffix, and never delete blind-test evidence.
- Dependencies: `skill-only` closeout remains dependency-free. Any new dependency or conda environment change for later experiments must be proposed explicitly before installation.
- Approval boundary: this proposal authorizes planning only. Architectural implementation requires the user to reply `Yes` before work begins.

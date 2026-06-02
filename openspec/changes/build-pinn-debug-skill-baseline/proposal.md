## Why

The PINN debugging handbook is now available as searchable Markdown, but Codex App does not yet have a reusable workflow that turns a user's training symptom into a disciplined diagnosis. A skill-only baseline is needed first so later MCP and hybrid-RAG experiments can be judged against a low-cost, dependency-free reference implementation.

## What Changes

- Add a self-contained Codex skill for PINN code debugging and module selection.
- Keep the first implementation intentionally lightweight: use `SKILL.md` instructions and Markdown references only.
- Package the handbook as an on-demand reference without introducing MCP servers, vector databases, embeddings, external APIs, or new conda dependencies.
- Require a symptom-first workflow: verify evidence, complete basic checks, recommend at most one next change, and define validation and rollback conditions.
- Add a small evaluation set that measures retrieval quality, diagnostic discipline, citation quality, and avoidance of premature module stacking.

## Capabilities

### New Capabilities

- `pinn-debug-skill-baseline`: Defines the dependency-free Codex skill baseline for PINN debugging, handbook lookup, module-selection guidance, and repeatable evaluation.

### Modified Capabilities

- None.

## Impact

- Affected area: the `exp/skill-only` worktree only.
- Expected new files: one Codex skill directory with `SKILL.md`, UI metadata, Markdown references, and baseline evaluation fixtures.
- Dependencies: reuse existing Codex App skill discovery and local text search. Do not install or modify conda packages.
- Data safety: keep the original handbook unchanged. Package a skill-local reference copy and verify its hash during implementation.
- Comparison role: use this branch as the baseline for the later `rules-mcp` and `hybrid-rag` worktrees.

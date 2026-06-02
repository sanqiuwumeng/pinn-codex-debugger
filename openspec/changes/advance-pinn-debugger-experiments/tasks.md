## 1. Implementation Preconditions

- [x] 1.1 Record whether the user wants a conda sandbox for implementation before starting the first development modification.
- [x] 1.2 Verify the active target worktree and review `git status` before each stage; do not create new worktrees or modify non-target worktrees.
- [x] 1.3 Preserve the source handbook hash `C7D3DD557F7942D6E10FE4331162297C07AF68AFFEC165066BC21CF8CE48EF16` as the comparison provenance baseline.

## 2. Close Out Skill-Only Baseline

- [x] 2.1 In `exp/skill-only`, create `baseline-results.md_backup_YYYY-MM-DD` before revising the existing baseline result record.
- [x] 2.2 Copy the existing external boundary-focused blind-test evidence into `validation/blind-tests/2026-06-02_boundary-auto-trigger/` without deleting or modifying the external source files.
- [x] 2.3 Update the repo-owned baseline result record to report the installed personal Skill, per-file hash match, and archived `3/3` auto-trigger blind-test result.
- [x] 2.4 Re-run Skill structural validation, fixture parsing, handbook provenance checks, personal-install hash comparison, and OpenSpec validation.
- [x] 2.5 Perform a first-principles review of the closeout diff, simplify any redundant release text, confirm Git scope, and create an intentional `exp/skill-only` commit.

## 3. Freeze Nine-Family Blind Benchmark

- [ ] 3.1 Create a canonical blind-suite manifest with at least one non-leaking user-style prompt for each of the nine required symptom families.
- [ ] 3.2 Store the canonical suite under `validation/blind-tests/<YYYY-MM-DD>_nine-family-baseline/` with the frozen rubric, prompt manifest, and result-record template.
- [ ] 3.3 Run each prompt in an isolated Codex App thread without naming the Skill, retrieval implementation, expected module, handbook anchor, or acceptance criteria.
- [ ] 3.4 Archive exact prompts, thread IDs, raw responses, and per-case scoring notes for every isolated thread.
- [ ] 3.5 Summarize symptom classification, basic checks, single-change discipline, metric and rollback quality, traceability, retrieval misses, synonym-expansion needs, module stacking, and response-concision deviations.
- [ ] 3.6 Re-run baseline validation, perform first-principles review and simplification of the benchmark artifacts, confirm Git scope, and create an intentional benchmark commit.

## 4. Prepare Rules-MCP Architecture Gate

- [ ] 4.1 Pause and obtain an explicit user reply of `Yes` before implementing the `rules-mcp` architecture.
- [ ] 4.2 Record the accepted sandbox and dependency plan before installing packages or changing any conda environment.
- [ ] 4.3 In `exp/rules-mcp`, integrate the reviewed baseline and frozen-benchmark commits without modifying the `exp/skill-only` worktree.
- [ ] 4.4 Review `git status` in `exp/rules-mcp` and back up every existing file before revision.

## 5. Implement Rules-MCP Retrieval

- [ ] 5.1 Scaffold a physically isolated local MCP server with explicit request and response schemas for symptom records and evidence extraction.
- [ ] 5.2 Implement deterministic handbook heading-range extraction that preserves source hash, heading, anchor, and line-range provenance despite inline HTML table noise.
- [ ] 5.3 Implement lookup-table and explicit synonym-rule routing for symptom family, evidence gaps, required basic checks, and candidate handbook anchors.
- [ ] 5.4 Add unit tests proving repeated requests return identical structured evidence and that the nine frozen families route to traceable handbook evidence.
- [ ] 5.5 Replay the frozen blind benchmark, archive raw comparison evidence, and report differences from `skill-only`.
- [ ] 5.6 Run the closed-loop review `Debug -> First-Principles Refactoring -> Simplification`, validate the MCP experiment, confirm Git scope, and create an intentional `exp/rules-mcp` commit.

## 6. Prepare Hybrid-RAG Architecture Gate

- [ ] 6.1 Pause and obtain an explicit user reply of `Yes` before implementing the `hybrid-rag` architecture or installing semantic-retrieval dependencies.
- [ ] 6.2 Select and record the local semantic backend, index format, package versions, resource cost, and sandbox plan.
- [ ] 6.3 In `exp/hybrid-rag`, integrate the reviewed baseline and frozen-benchmark commits; explicitly decide whether the hybrid layer reuses the deterministic extractor through an isolated boundary.
- [ ] 6.4 Review `git status` in `exp/hybrid-rag` and back up every existing file before revision.

## 7. Implement Hybrid-RAG Retrieval

- [ ] 7.1 Scaffold a physically isolated retrieval adapter with explicit query input and ranked-section output schemas.
- [ ] 7.2 Build a reproducible handbook section index that records source hash, heading, anchor, section text boundary, and semantic-index inputs.
- [ ] 7.3 Implement semantic recall for paraphrased symptoms and deterministic source traceability for every ranked result.
- [ ] 7.4 Implement section ranking so focused handbook sections outrank generic mentions of common module names.
- [ ] 7.5 Add tests for unseen paraphrases, repeated ranking behavior, provenance, and noisy Markdown section handling.
- [ ] 7.6 Replay the frozen blind benchmark plus paraphrase variants, archive raw evidence, and compare `hybrid-rag` against both preceding branches.
- [ ] 7.7 Run the closed-loop review `Debug -> First-Principles Refactoring -> Simplification`, validate the hybrid experiment, confirm Git scope, and create an intentional `exp/hybrid-rag` commit.

## 8. Final Comparison

- [ ] 8.1 Produce a three-branch comparison report covering diagnostic quality, retrieval quality, traceability, dependency cost, runtime cost, and known failure cases.
- [ ] 8.2 Verify that source handbook content remains unchanged and that all experiment evidence is preserved.
- [ ] 8.3 Review whether the completed OpenSpec change is ready to archive without deleting any user data.

## Context

The repository has one handbook baseline commit and three existing experiment worktrees:

```text
exp/skill-only  -> text-only Codex skill baseline
exp/rules-mcp   -> deterministic structured-retrieval experiment
exp/hybrid-rag  -> semantic retrieval and ranking experiment
```

The `skill-only` implementation is complete but uncommitted. Its installed personal-skill copy matches the repo-owned copy byte-for-byte, while `evals/baseline-results.md` still describes the pre-installation state. A separate `skill_test` directory contains three isolated boundary-focused blind tests that have not been archived into the branch.

The comparison is only meaningful if later experiments use the same handbook provenance, prompt fixtures, scoring rubric, and response contract. The two richer experiments also need strict physical isolation so their behavior can be attributed to their own retrieval method.

## Goals / Non-Goals

**Goals:**

- Produce a committed, auditable `skill-only` baseline release.
- Freeze a nine-family blind-test benchmark with raw evidence and comparable scoring.
- Add a deterministic `rules-mcp` experiment with structured symptom records and traceable evidence extraction.
- Add a `hybrid-rag` experiment that improves paraphrase recall and section ranking while preserving traceability.
- Keep each functional module physically isolated and pass data through explicit request and response objects.
- Require explicit user approval before architectural implementation and before any dependency installation.

**Non-Goals:**

- Do not create new worktrees.
- Do not modify the source handbook content.
- Do not place blind-test process records inside the portable skill package.
- Do not add compatibility layers, global variables, singletons, or implicit cross-module state.
- Do not install packages, create conda environments, or choose a semantic-retrieval backend during proposal generation.

## Decisions

### Decision 1: Advance in gated stages

Implement the sequence strictly:

1. release `skill-only`;
2. freeze and run the nine-family blind benchmark;
3. implement and compare `rules-mcp`;
4. implement and compare `hybrid-rag`.

Each stage must finish validation before the next begins. Architectural stages 3 and 4 require a fresh explicit user reply of `Yes`.

Alternative considered: build all three branches in parallel. Rejected because the baseline and benchmark would continue moving while comparisons were being implemented.

### Decision 2: Archive blind-test evidence outside the portable skill

Store branch-owned validation evidence under:

```text
validation/blind-tests/<YYYY-MM-DD>_<suite-name>/
```

Keep exact prompts, thread IDs, raw responses, scoring notes, and a suite summary. Copy existing `skill_test` evidence into the branch-owned archive without deleting the original files.

Alternative considered: store blind-test records under `skills/pinn-debugging-assistant/evals/`. Rejected because installed skills should contain reusable execution resources, not project-history artifacts.

### Decision 3: Freeze one comparison benchmark

Create one canonical nine-family blind suite derived from the existing reusable fixtures. Prompts must avoid naming the skill, retrieval implementation, expected module, or acceptance criteria. Apply the same rubric to `skill-only`, `rules-mcp`, and `hybrid-rag`.

Record both diagnosis quality and retrieval behavior:

- symptom family;
- basic-check discipline;
- one-change discipline;
- metric and rollback quality;
- handbook traceability;
- anchors or sections retrieved;
- zero-match anchors;
- synonym expansion required;
- multi-module stacking;
- response concision deviations.

Alternative considered: let each branch use optimized prompts. Rejected because branch-specific prompts would weaken comparison validity.

### Decision 4: Use an isolated deterministic retrieval boundary for `rules-mcp`

The `rules-mcp` worktree will add a local MCP server with an explicit request and response schema. The request carries the observable symptom and optional evidence. The response returns a structured symptom record, deterministic matching evidence, handbook headings or anchors, and unresolved evidence gaps.

The implementation must remain deterministic: handbook parsing, lookup tables, heading ranges, and keyword or synonym rules are allowed; embeddings and semantic vector search are not.

Alternative considered: extend the Skill with more inline routing tables. Rejected because the experiment is intended to measure the value of structured extraction behind a stable tool boundary.

### Decision 5: Keep `hybrid-rag` retrieval isolated behind an explicit adapter

The `hybrid-rag` worktree will add a local retrieval component that accepts a query plus optional symptom metadata and returns ranked handbook sections with source anchors and scores. It must combine semantic recall with deterministic source traceability and must not silently fall back to unrelated sections.

The semantic backend, index storage, and package set remain implementation decisions to resolve after the user approves the architecture and chooses whether to create a conda sandbox.

Alternative considered: choose an embedding model now. Rejected because backend selection affects dependencies, reproducibility, and local resource cost.

### Decision 6: Preserve one-change diagnostic discipline across branches

Retrieval improvements may improve evidence quality but must not alter the response contract: diagnose from observable evidence, run relevant basic checks, recommend at most one next logical intervention, name an expected metric, state rollback conditions, and cite a handbook anchor.

Alternative considered: let richer retrieval return larger module menus. Rejected because module stacking would confound diagnosis quality with retrieval breadth.

## Risks / Trade-offs

- [Risk] Existing handbook Markdown contains noisy inline HTML tables and malformed headings. -> Mitigation: preserve the source unchanged, extract explicit heading ranges, and record parsing misses.
- [Risk] Blind-test responses may vary between threads. -> Mitigation: store raw responses, run isolated threads, score with a fixed rubric, and report deviations rather than hiding them.
- [Risk] Deterministic rules may overfit the frozen prompts. -> Mitigation: keep blind prompts separate from implementation artifacts and include paraphrased variants in evaluation.
- [Risk] Semantic retrieval may add dependencies or nondeterminism. -> Mitigation: require dependency approval, record versions and index inputs, and keep the deterministic benchmark unchanged.
- [Risk] Cross-worktree edits may accidentally mix experiment artifacts. -> Mitigation: operate in one target worktree at a time and verify `git status` before each commit.

## Migration Plan

1. In `exp/skill-only`, back up every existing file before revision, copy blind-test evidence into `validation/blind-tests/`, update release records, validate, and commit.
2. Add and run the frozen nine-family blind suite in `exp/skill-only`, preserve raw evidence, validate, and commit.
3. After explicit `Yes`, implement `rules-mcp` only in `exp/rules-mcp`, replay the frozen benchmark, and commit comparison results.
4. After explicit `Yes`, resolve the semantic backend and dependencies, implement `hybrid-rag` only in `exp/hybrid-rag`, replay the frozen benchmark, and commit comparison results.
5. If an experiment fails its validation gate, retain its evidence, revert only that experiment's new implementation changes with user approval, and keep the preceding committed stage as the comparison baseline.

## Open Questions

- Should later implementations use a dedicated conda sandbox, and if so, should `rules-mcp` and `hybrid-rag` share one sandbox or use separate sandboxes?
- Which local semantic backend and index format should `hybrid-rag` use after architecture approval?
- Should the project keep the current external `skill_test` directory permanently after its evidence has been copied into the branch-owned archive?

## Context

The repository currently contains a Markdown conversion of the PINN debugging handbook and no Codex skill implementation. The handbook is large enough that loading it in full for every debugging request would waste context, but its chapter structure, symptom tables, module-selection guidance, diagnostic cards, and field checklists are suitable for progressive disclosure.

This branch is the control experiment for later `rules-mcp` and `hybrid-rag` worktrees. It must remain dependency-free and easy to inspect. The implementation must not change the existing `pytorch2.3.1` conda environment, install packages, start a server, or depend on a network service.

## Goals / Non-Goals

**Goals:**

- Create a self-contained Codex App skill that activates for PINN debugging, training-failure analysis, and module-selection requests.
- Guide Codex through symptom description, evidence collection, basic checks, one logical intervention, validation metrics, and rollback conditions.
- Use progressive disclosure so the skill loads a compact routing reference first and searches the full handbook only when needed.
- Preserve handbook provenance by keeping a byte-identical skill-local reference copy and documenting its source hash.
- Add repeatable evaluation fixtures that can also be reused by the later MCP and hybrid-RAG branches.

**Non-Goals:**

- Do not build an MCP server, database, embedding pipeline, reranker, knowledge graph, or UI.
- Do not install the skill globally into `C:\Users\Mli\.codex\skills` during implementation. Validate the repo-owned skill first.
- Do not change or install conda packages.
- Do not automatically modify a user's PINN code merely because a diagnosis was requested.
- Do not claim that a module is effective unless the response names supporting evidence and a validation metric.

## Decisions

### Decision 1: Package a repo-owned, self-contained skill

Create `skills/pinn-debugging-assistant/` with:

```text
SKILL.md
agents/openai.yaml
references/routing-index.md
references/PINN报错诊断与模块选择手册.md
evals/cases.jsonl
evals/rubric.md
```

The complete handbook copy stays inside the skill so the folder can later be installed or bundled without depending on a repository-relative file outside the skill.

Alternative considered: point the skill directly at the repository-root handbook. Rejected because the skill would stop working when copied into Codex App's personal skill directory.

### Decision 2: Use two-level Markdown retrieval

`SKILL.md` SHALL instruct Codex to read `references/routing-index.md` first, then use `rg` against the full handbook for relevant keywords, chapter names, or module names. The routing index SHALL summarize symptom families, basic-check order, output format, and useful search patterns without duplicating the handbook's detailed prose.

Alternative considered: load the complete handbook on every trigger. Rejected because it consumes unnecessary context and weakens the baseline's efficiency.

### Decision 3: Enforce a diagnosis contract

The skill SHALL structure diagnostic responses around:

1. Observable symptom.
2. Evidence already available and evidence still missing.
3. Mandatory basic checks.
4. One next logical change only.
5. Expected metric improvement.
6. Rollback condition.
7. Handbook reference path and heading.

Alternative considered: return a ranked list of many modules immediately. Rejected because the handbook explicitly prioritizes basic checks and single-factor experiments.

### Decision 4: Keep the baseline text-only

The skill MAY inspect user-provided code, logs, and image descriptions using normal Codex capabilities, but it SHALL NOT add custom scripts, parsers, or runtime dependencies in this branch.

Alternative considered: add Python scripts for static analysis and log parsing. Deferred to a later experiment because that would make the baseline harder to compare against richer branches.

### Decision 5: Use fixture-driven evaluation

Add a shared JSONL evaluation set and a Markdown rubric. Cases SHALL cover at least boundary-condition failure, late-time divergence, local residual hotspots, high-frequency smoothing, inverse-parameter drift, conservation drift, high-order PDE instability, repeated parametric solves, and one deliberately underspecified symptom.

The rubric SHALL score:

- correct symptom family;
- completion of basic checks before module recommendation;
- one-change discipline;
- metric and rollback quality;
- handbook citation quality;
- refusal to overdiagnose underspecified cases.

Alternative considered: judge the skill only through informal manual use. Rejected because later branches need the same measurable baseline.

## Risks / Trade-offs

- [Risk] Keyword search may miss paraphrased user descriptions. -> Mitigation: include synonym-oriented search patterns in the routing index and measure misses for later RAG comparison.
- [Risk] A compact routing index may accidentally become a second source of truth. -> Mitigation: keep it as navigation guidance and require detailed claims to cite handbook headings.
- [Risk] The handbook copy may drift from the repository-root source. -> Mitigation: verify and record the source SHA256 during implementation.
- [Risk] Skill triggering may be too narrow or too broad. -> Mitigation: include concrete trigger phrases in the `description` field and test representative prompts.
- [Risk] Text-only diagnosis cannot automatically inspect runtime tensors or plots. -> Mitigation: state missing evidence clearly and reserve runtime inspection for later branches.

## Migration Plan

1. Build and validate the repo-owned skill under `exp/skill-only`.
2. Run the fixed evaluation fixtures and record baseline observations.
3. Install or package the skill for Codex App only after explicit user approval.
4. If the baseline is rejected, remove the skill directory and OpenSpec change without touching the original handbook or conda environments.

## Open Questions

- After baseline evaluation, should the installed artifact remain a personal skill or be wrapped in a distributable plugin?
- Which failure cases show enough keyword-retrieval weakness to justify the `hybrid-rag` branch?
- Which repeated code-inspection tasks justify deterministic scripts or MCP tools in the `rules-mcp` branch?

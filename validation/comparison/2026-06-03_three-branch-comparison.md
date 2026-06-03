# Three-Branch PINN Debugger Comparison

## Scope

- Date: `2026-06-03`
- Branches compared: `exp/skill-only`, `exp/rules-mcp`, `exp/hybrid-rag`
- Frozen suite: `validation/blind-tests/2026-06-02_nine-family-baseline/prompts.jsonl`
- Handbook SHA256: `C7D3DD557F7942D6E10FE4331162297C07AF68AFFEC165066BC21CF8CE48EF16`

## Results

| Branch | Retrieval / diagnosis target | Frozen result | Paraphrase result | Dependency cost |
| --- | --- | ---: | ---: | --- |
| `skill-only` | End-to-end Codex Skill response quality | `86 / 90` blind score | Not run | Installed Skill files only |
| `rules-mcp` | Deterministic symptom family and handbook evidence | `9 / 9` family routing | Not run | Python standard library only |
| `hybrid-rag` | Same frozen suite plus synonym recall and chapter ordering | `9 / 9` family, `9 / 9` top heading | `9 / 9` family, `9 / 9` top heading | Python standard library only |

## Interpretation

- `skill-only` is already strong for response quality, but it has response-concision drift and two minor discipline deviations in the frozen blind suite.
- `rules-mcp` provides stable, traceable structured retrieval with source hash, heading, matched anchors, and line ranges.
- `hybrid-rag` preserves the rules boundary and improves synonym/paraphrase recall before installing any neural embedding dependency.
- The hybrid backend solves the current target problem: paraphrased symptoms retrieve the intended handbook chapter, and focused chapters outrank generic module mentions.

## Known Failure Cases

- `skill-only` can answer too broadly because response generation is not structurally constrained by a tool schema.
- `rules-mcp` depends on explicit keywords and curated synonym rules, so unseen paraphrases can require more catalog work.
- `hybrid-rag` is deterministic lexical-semantic retrieval, not neural embedding retrieval; it should be treated as the zero-dependency hybrid baseline before any heavier semantic backend.

## Archive Readiness

- Source handbook content remained unchanged.
- Branch-owned validation evidence is preserved under `validation/`.
- Backups for modified existing files are stored under the OpenSpec change backups directory.
- The OpenSpec change is ready for review before archival; archival itself should not delete evidence or external user data.

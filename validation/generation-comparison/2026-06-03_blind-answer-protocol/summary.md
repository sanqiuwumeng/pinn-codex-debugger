# Uniform Blind Answer Protocol Comparison

- Date: `2026-06-03`
- Frozen prompt suite: `validation/blind-tests/2026-06-02_nine-family-baseline/prompts.jsonl`
- Scoring rubric: `validation/blind-tests/2026-06-02_nine-family-baseline/rubric.md`

## Scores

| Scheme | Run type | Score | Notes |
| --- | --- | ---: | --- |
| `skill-only` | `archived-isolated-thread` | `86 / 90` | Existing raw blind response and scoring notes from the frozen skill-only baseline. |
| `rules-mcp` | `reproducible-protocol-adapter` | `90 / 90` | Generated from SymptomRecord through the frozen answer protocol. |
| `hybrid-rag` | `reproducible-protocol-adapter` | `90 / 90` | Generated from rules family plus hybrid ranked sections through the frozen answer protocol. |

## Interpretation

- `skill-only` is the archived end-to-end blind-thread baseline.
- `rules-mcp` and `hybrid-rag` are scored as protocol adapters: retrieval output is passed through the same frozen response contract.
- These results show the answer-quality ceiling under a controlled protocol; a fresh LLM-thread rerun would still be needed for nondeterministic production behavior.

# PINN Debugging Baseline Rubric

Apply this rubric unchanged to `skill-only`, `rules-mcp`, and `hybrid-rag`.

## Per-Case Score

Score each case from `0` to `10`.

| Criterion | Points | Pass condition |
| --- | ---: | --- |
| Symptom family | 2 | Identify the expected symptom family without jumping directly to an unrelated module. |
| Basic checks | 2 | Name the relevant basic checks before the enhancement recommendation. |
| One-change discipline | 2 | Recommend at most one logical intervention for the next experiment. |
| Metric and rollback | 2 | Name an expected metric and a clear condition for reverting to baseline. |
| Traceability | 2 | Cite the handbook reference and a relevant heading or search anchor. |

## Underspecified Case

For `underspecified-failure`, award full credit only when the response requests concrete evidence and does not recommend an enhancement module.

## Aggregate Metrics

Record:

- total score and score percentage;
- per-case score;
- search anchors used;
- anchors with zero matches;
- cases requiring manual synonym expansion;
- overdiagnosis count;
- multi-module stacking count;
- missing rollback count;
- missing handbook-anchor count.

## Comparison Rule

Use the exact same prompts and rubric for later branches. Do not improve `skill-only` with MCP, embeddings, databases, or custom scripts after baseline recording; create a separate experiment instead.

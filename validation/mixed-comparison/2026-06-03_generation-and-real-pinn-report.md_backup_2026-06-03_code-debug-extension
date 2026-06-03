# Mixed Comparison: Blind Answer Protocol And Real PINN-2D Debugging

## Scope

- Date: `2026-06-03`
- Round 1: uniform answer-generation protocol over the frozen nine-family blind suite.
- Round 2: controlled read-only debugging of `skill_test\PINN-2D` by three isolated subagents.
- Environment: existing `pytorch2.3.1`; no conda sandbox; no new external packages.

## Round 1 Results

| Scheme | Result | Meaning |
| --- | ---: | --- |
| `skill-only` | `86 / 90` | Archived end-to-end blind-thread score from the original frozen suite. |
| `rules-mcp` | `90 / 90` | Protocol-adapter score using deterministic `SymptomRecord` evidence. |
| `hybrid-rag` | `90 / 90` | Protocol-adapter score using rules family plus hybrid ranked sections. |

Round 1 indicates that once `rules-mcp` and `hybrid-rag` are constrained by the same answer contract, they avoid the two `skill-only` deviations: broad experiment matrix and conditional module suggestion for an underspecified case. This is a controlled protocol result, not yet a fresh end-to-end LLM blind-thread result.

## Round 2 Results

| Scheme | Result | Main observation |
| --- | ---: | --- |
| `skill-only` | `10 / 10` | Directly identified the `t=5.0` phase-interface/local-error issue and rejected boundary as primary cause. |
| `rules-mcp` | `10 / 10` | Corrected the structured `underspecified` record using the case packet; useful conflict handling, but the catalog needs stronger real-case terms. |
| `hybrid-rag` | `10 / 10` | Corrected top-ranked boundary retrieval bias and explicitly re-ranked evidence by validated case facts. |

All three agents converged on the same practical conclusion: the next diagnostic action is a read-only `t=5.0` phase-interface/local sampling and residual audit, not retraining or module stacking.

## Overall Conclusion

- `rules-mcp` and `hybrid-rag` now outperform `skill-only` in Round 1 under a controlled answer-generation protocol: `90 / 90` vs `86 / 90`.
- On the real PINN-2D case, all three schemes tied numerically at `10 / 10`; there is no score-based winner.
- Qualitatively, `hybrid-rag` gave the best self-audit of retrieval ranking bias, `rules-mcp` revealed the clearest catalog weakness, and `skill-only` was the cleanest direct diagnosis.

## Failure Modes To Fix Next

- `rules-mcp`: English real-case prompts and metrics-rich descriptions can fall through to `underspecified`; add deterministic terms for time-slice metrics, phase interface, liquid mask, and localized early-time error.
- `hybrid-rag`: validated boundary-condition mentions can over-rank boundary sections; ranking should down-weight sections whose premise is explicitly contradicted by supplied evidence.
- `skill-only`: still needs structure enforcement if used without a protocol adapter, because the original blind suite showed over-broad response tendencies.

## Recommended Next Step

Improve retrieval adapters before running another expensive blind-thread round:

1. Add explicit evidence-aware conflict handling to `rules-mcp` and `hybrid-rag`.
2. Add real-case vocabulary around phase-interface error, liquid mask IoU, melted-area ratio, and time-slice metrics.
3. Re-run the same mixed comparison to see whether retrieval records align with the agents' corrected diagnoses.

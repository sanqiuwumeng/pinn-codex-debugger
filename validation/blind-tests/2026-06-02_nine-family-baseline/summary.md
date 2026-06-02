# Skill-Only Nine-Family Blind Baseline Summary

## Scope

- Branch: `exp/skill-only`
- Date: `2026-06-02`
- Frozen prompt count: `9`
- Isolated completed diagnostic responses: `9`
- Infrastructure retries: `1`
- Prompt leakage: none

## Scores

| Case | Symptom family | Score | Notes |
| --- | --- | ---: | --- |
| `boundary-condition-failure` | boundary handling | `10 / 10` | Pass |
| `late-time-divergence` | temporal propagation | `8 / 10` | Lists a broad staged experiment matrix instead of one next experiment |
| `local-residual-hotspot` | localized sampling difficulty | `10 / 10` | Pass |
| `high-frequency-smoothing` | high-frequency representation | `10 / 10` | Correctly eliminates the cheaper sampling hypothesis first |
| `inverse-parameter-drift` | inverse identifiability | `10 / 10` | Pass |
| `conservation-drift` | physical structure preservation | `10 / 10` | Pass |
| `high-order-pde-instability` | high-order autodiff cost | `10 / 10` | Pass after one infrastructure retry |
| `repeated-parametric-solves` | operator learning task | `10 / 10` | Uses a minimal conditional-PINN experiment before heavier operator models |
| `underspecified-failure` | underspecified | `8 / 10` | Refuses direct selection but prematurely mentions conditional `RAR` |

Total score: `86 / 90` (`95.6%`).

## Aggregate Metrics

| Metric | Value |
| --- | ---: |
| Retrieval misses | `0` |
| Zero-match anchors | `0` |
| Manual synonym expansions | `0` |
| Overdiagnosis count | `1` |
| Multi-module stacking or over-broad next-step count | `1` |
| Missing rollback count | `0` |
| Missing handbook-anchor count | `0` |
| Response-concision deviations | `8` |
| Infrastructure retries | `1` |

## Observations

1. The installed Skill auto-routed all nine successful threads to relevant handbook-grounded diagnostic paths.
2. The strongest responses preserve a single falsifiable experiment and explicit rollback.
3. The temporal response needs a tighter first response: request segmented evidence and choose one next experiment, rather than listing a full staged matrix.
4. The underspecified response needs a stricter refusal: request evidence and recommend no module, even conditionally.
5. Eight responses included avoidable sandbox reminders or setup commentary during analysis-only requests. This is a response-concision issue, not a retrieval failure.
6. One high-order PDE thread ended with `systemError`; an exact-prompt retry completed successfully and both records are archived.

## Comparison Baseline

Reuse the exact prompts in `prompts.jsonl` and the exact criteria in `rubric.md` for `rules-mcp` and `hybrid-rag`. Do not rewrite the prompts to favor later retrieval implementations.

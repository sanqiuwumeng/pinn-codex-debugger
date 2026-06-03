# Real PINN-2D Three-Scheme Scoring

## Rubric

Each scheme is scored out of 10:

- 2: correctly identifies that boundary/initial constraints are already validated.
- 2: prioritizes the dominant observed error pattern from the provided metrics.
- 2: chooses one next diagnostic step, not a module stack.
- 1: names expected metric movement.
- 1: states rollback or falsification criteria.
- 1: cites relevant handbook evidence.
- 1: avoids modifying or retraining the model during diagnosis.

## Scores

| Scheme | Score | Notes |
| --- | ---: | --- |
| `skill-only` | `10 / 10` | Correctly rejected boundary as primary cause, focused on `t=5.0` phase-interface/local residual evidence, and gave one read-only diagnostic step. |
| `rules-mcp` | `10 / 10` | Detected that the rules record under-specified the case, overrode it with case-packet evidence, and focused on local phase/interface diagnostics. |
| `hybrid-rag` | `10 / 10` | Explicitly identified the top-ranked boundary section as retrieval bias, re-ranked evidence by case facts, and selected the phase-interface/local sampling audit. |

## Qualitative Differences

- `skill-only` produced the most direct diagnosis without tool bias, but it relies on the model following the skill discipline.
- `rules-mcp` exposed a catalog/input-language weakness: the structured record labeled the English real-case prompt as `underspecified`, but the subagent corrected it from the packet.
- `hybrid-rag` exposed a ranking weakness: the top section was boundary handling because the packet mentions validated constraints, but the subagent explicitly down-ranked that conflict.

## Shared Diagnostic Conclusion

All three schemes converged on the same next diagnostic step: perform a read-only audit of `t=5.0` near the early melt interface, comparing temperature error, liquid-mask mismatch, PDE residual concentration, and sampling coverage around the `1878-1928 K` phase-change band. Do not modify or retrain the model until that evidence confirms the dominant failure mode.

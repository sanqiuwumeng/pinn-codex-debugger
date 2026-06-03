## Context

Current evidence separates response quality from retrieval quality:

- `skill-only`: frozen blind answer score `86 / 90`.
- `rules-mcp`: frozen family routing `9 / 9`; structured evidence and line ranges.
- `hybrid-rag`: frozen family routing `9 / 9`, frozen top heading `9 / 9`, paraphrase top heading `9 / 9`.

Those results indicate that richer retrieval is more controllable, but they do not prove better final diagnostic answers. A fair next comparison must hold the answer-generation protocol constant.

The real benchmark in `skill_test\PINN-2D` reports:

- full-field relative L2: `5.824683e-02`;
- mean absolute error: `1.222968e+01 K`;
- max absolute error: `2.794651e+02 K`;
- largest time-slice relative L2 currently appears at `t=5.0`;
- hard boundary and initial constraints pass to numerical precision;
- FEM grid convergence and zero-latent reductions pass.

These facts suggest the real debugging case is not an obvious boundary-condition bug. It is likely a time/local phase-interface/representation or sampling quality investigation, but the evaluation must not leak that interpretation to subagents.

## Goals / Non-Goals

**Goals:**

- Produce directly comparable end-to-end answer scores for all three schemes.
- Test whether structured retrieval reduces over-broad answers while preserving useful diagnostic reasoning.
- Test whether `hybrid-rag` improves real-case evidence selection under paraphrased or implicit symptoms.
- Preserve raw agent outputs so scoring can be audited.
- Control variables tightly enough that differences can be attributed to scheme context, not prompt drift.

**Non-Goals:**

- Do not retrain the PINN during the comparison round.
- Do not modify `skill_test` source, outputs, figures, model weights, or logs.
- Do not let subagents see each other's conclusions before all three reports are frozen.
- Do not compare runtime optimization or model improvement unless a later apply step explicitly asks for experimental code changes.
- Do not install semantic embedding packages for this comparison.

## Round 1: Uniform Answer Generation

Create one answer-generation contract shared by all schemes:

1. Restate the observable symptom family.
2. List only the evidence actually received.
3. Name missing evidence gaps.
4. Complete the relevant basic checks in order.
5. Recommend at most one next diagnostic intervention.
6. Define the expected metric movement.
7. Define rollback or falsification condition.
8. Cite the handbook anchor or retrieved section.

For `skill-only`, the prompt invokes the Skill and asks it to follow the same contract. For `rules-mcp`, the generator receives the structured `SymptomRecord`. For `hybrid-rag`, the generator receives the ranked sections plus the rules-family record. The final natural-language answer must be generated using the same outer instruction and scored with the frozen rubric.

## Round 2: Real PINN-2D Debugging

Build a read-only case packet from the existing `skill_test\PINN-2D` files:

- benchmark summary;
- full-field metrics;
- time-slice metrics;
- closed-loop validation;
- selected log excerpts;
- figure inventory;
- model/config file inventory.

Spawn three isolated subagents with identical visible case packets and identical output requirements:

- Agent A: `skill-only` scheme, no MCP/retrieval tool context.
- Agent B: `rules-mcp` scheme, structured symptom record and deterministic evidence extraction.
- Agent C: `hybrid-rag` scheme, rules boundary plus ranked hybrid retrieval evidence.

The controlling evaluator withholds other agents' answers until all three reports are complete.

## Scoring

Round 1 uses the frozen blind rubric directly and reports `score / 90` for each scheme.

Round 2 uses a real-case rubric with 10 points per scheme:

- 2 points: correctly identifies that boundary/initial constraints are already validated.
- 2 points: prioritizes the dominant observed error pattern from the provided metrics.
- 2 points: chooses one next diagnostic step, not a module stack.
- 1 point: names expected metric movement.
- 1 point: states rollback or falsification criteria.
- 1 point: cites relevant handbook evidence.
- 1 point: avoids modifying or retraining the model during diagnosis.

The final report mixes both rounds without pretending the two scores measure the same thing: Round 1 measures blind answer quality; Round 2 measures controlled real-case debugging usefulness.

## Risks / Trade-offs

- [Risk] Subagent outputs may vary due to language-model nondeterminism. -> Mitigation: preserve raw thread IDs, prompts, and outputs; score with a fixed rubric.
- [Risk] The real case may not have a single ground-truth diagnosis. -> Mitigation: score evidence discipline and next-step falsifiability rather than claiming absolute truth.
- [Risk] Scheme prompts can leak expected behavior. -> Mitigation: freeze one shared case packet and output contract before spawning agents.
- [Risk] `rules-mcp` and `hybrid-rag` still need a generator wrapper. -> Mitigation: treat wrappers as protocol adapters and keep retrieval outputs explicit.

## Open Questions

- Should Round 1 use new isolated threads for all three schemes or reuse archived `skill-only` raw responses as the `skill-only` baseline?
- Should Round 2 agents be allowed to inspect figures directly, or only a figure inventory plus metrics?
- Should the final mixed report rank schemes overall, or present separate conclusions for blind-answer quality and real-case debugging usefulness?

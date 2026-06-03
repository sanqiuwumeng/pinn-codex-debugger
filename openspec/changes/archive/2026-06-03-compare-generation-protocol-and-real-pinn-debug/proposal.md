## Why

The previous experiment proved retrieval and traceability differences across `skill-only`, `rules-mcp`, and `hybrid-rag`, but it did not prove that `rules-mcp` or `hybrid-rag` produce better end-to-end diagnostic answers than `skill-only`. `skill-only` has a blind response score (`86 / 90`), while the richer branches currently have retrieval metrics (`9 / 9` routing or top-heading accuracy). These metrics are not directly comparable.

The project also has a real PINN benchmark under `E:\vibe coding\pinn-codex-debugger.worktrees\skill_test\PINN-2D`, including source code, logs, trained model output, FEM reference data, metrics, and figures. That case should be used as a controlled practical debugging test rather than only relying on synthetic prompts.

## What Changes

- Round 1: connect `rules-mcp` and `hybrid-rag` to the same answer-generation protocol and run the same frozen blind prompts with the same scoring rubric used for `skill-only`.
- Round 2: inspect the real `PINN-2D` benchmark directory and run three isolated subagents, one per scheme: `skill-only`, `rules-mcp`, and `hybrid-rag`.
- Keep Round 2 controlled by giving each subagent the same case packet, same budget, same requested output contract, and no access to the other agents' conclusions.
- Preserve raw prompts, thread IDs, retrieved evidence, generated answers, scoring notes, and a mixed final report that combines both rounds.
- Do not modify the `skill_test` model, result files, or source data unless a later implementation request explicitly asks for edits.

## Capabilities

### New Capabilities

- `pinn-debug-generation-comparison`: Defines a uniform answer-generation protocol and comparable blind scoring for all three schemes.
- `real-pinn-debug-comparison`: Defines a controlled real-case debugging comparison over the existing `PINN-2D` benchmark with three isolated subagents.

### Modified Capabilities

- None.

## Impact

- Affected worktree: `exp/hybrid-rag` for orchestration scripts, protocols, prompts, and validation evidence.
- External test data read target: `E:\vibe coding\pinn-codex-debugger.worktrees\skill_test\PINN-2D`.
- Expected new evidence locations:
  - `validation/generation-comparison/<YYYY-MM-DD>_blind-answer-protocol/`
  - `validation/real-pinn-debug/<YYYY-MM-DD>_pinn-2d-three-scheme/`
- Data safety: read-only inspection of `skill_test` during proposal and evaluation; copy only needed summaries into validation artifacts; never delete or overwrite model outputs.
- Dependencies: no package installation is proposed for Round 1. Round 2 should initially reuse the existing local environment and existing subagent/thread tooling.
- Approval boundary: this proposal authorizes planning only. Implementation, subagent spawning, or any protocol/runner code changes require a later apply step.

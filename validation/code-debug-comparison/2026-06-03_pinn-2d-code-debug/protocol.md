# PINN-2D Code Debug Comparison Protocol

## Scope

- Date: `2026-06-03`
- Source case: `E:\vibe coding\pinn-codex-debugger.worktrees\skill_test\PINN-2D`
- Experiment root: `validation/code-debug-comparison/2026-06-03_pinn-2d-code-debug`
- Runtime: existing `pytorch2.3.1` conda environment
- Sandbox: no new conda sandbox

## Isolation

Each scheme receives a private copy under:

- `workspaces/skill-only`
- `workspaces/rules-mcp`
- `workspaces/hybrid-rag`

Agents may modify only their assigned workspace. They must not modify the original `skill_test\PINN-2D` directory or another scheme's workspace.

## Allowed Actions

- Inspect source code, logs, metrics, and figures in the assigned workspace.
- Make one logical code or configuration change intended to improve the diagnosed failure mode.
- Run training or validation commands inside the assigned workspace.
- Record exact commands, changed files, and before/after metrics.

## Required Output

Each agent must report:

1. Scheme
2. Diagnosis used to choose the code change
3. Files changed
4. Exact commands run
5. Before metrics
6. After metrics
7. Whether the change improved the target metric
8. Any regressions
9. Patch or concise diff summary

## Shared Target

The practical target is the early phase-interface error observed at `t=5.0`:

- `relative_l2 = 0.1186936363`
- `melted_area_relative_error = 0.4666666667`
- `liquid_mask_iou = 0.6818181818`
- `max_abs_error = 279.4650854 K`

Agents should keep changes minimal and comparable. A smoke-mode retrain is acceptable for this first code-debug comparison; full 3000-epoch training is not required unless the agent can justify and complete it within its own budget.

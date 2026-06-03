# PINN-2D Code Debug Comparison

## Scope

- Date: `2026-06-03`
- Source copied from: `E:\vibe coding\pinn-codex-debugger.worktrees\skill_test\PINN-2D`
- Workspaces are ignored from Git: `workspaces/`
- Environment: `pytorch2.3.1`
- Original source directory was not modified.

## Comparability Warning

`skill-only` and `hybrid-rag` both produced full-training after results. `rules-mcp` produced smoke-mode after results only. Therefore:

- Compare `skill-only` and `hybrid-rag` directly on full metrics.
- Treat `rules-mcp` as a useful smoke/debug exploration, not as a full-result competitor.

## Full-Training Results

| Scheme | Change | Full L2 | Full MAE K | Full max K | `t=5` L2 | `t=5` MAE K | `t=5` max K | `t=5` melted err | `t=5` IoU |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | Original | `0.05825` | `12.23` | `279.47` | `0.11869` | `22.80` | `279.47` | `0.4667` | `0.6818` |
| `skill-only` | 33% focused sampling | `0.06689` | `17.99` | `154.40` | `0.12027` | `32.16` | `154.40` | `0.2000` | `0.8333` |
| `hybrid-rag` | 12.5% stratified focused sampling | `0.04960` | `13.22` | `122.49` | `0.08874` | `25.26` | `122.49` | `0.0000` | `1.0000` |

## Smoke-Only Rules-MCP Result

| Scheme | Change | Smoke full L2 | Smoke `t=5` L2 | Smoke `t=5` melted err | Smoke `t=5` IoU | Regression |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `rules-mcp` | `eta**2` to `eta**4` hard-constraint lifting | `1.01236` | `0.54373` | `0.0000` | `1.0000` | `t=40` L2 worsened from `1.40994` to `1.54500` |

## Ranking

1. `hybrid-rag`: best full-training result and best use of diagnostic evidence. It tested focus strengths and settled on a lighter 12.5% focus after heavier focus hurt global metrics.
2. `skill-only`: found the same failure mode and ran a full retrain, but used a heavier 33% focus that improved geometry while worsening global field metrics.
3. `rules-mcp`: found a plausible minimal ansatz change and improved smoke early-interface metrics, but did not complete a full comparable retrain and showed late-time regression in smoke mode.

## Conclusion

For code-debugging assistance in this PINN-2D case, `hybrid-rag` was the most effective. Its advantage was not just retrieval recall; it used retrieved evidence to identify and down-weight a boundary-condition false lead, then tuned the intervention strength through controlled full runs. `skill-only` diagnosed the same issue but picked a more aggressive sampling change. `rules-mcp` gave a useful alternate hypothesis, but the available evidence is smoke-only.

## Next Engineering Step

Promote the `hybrid-rag` 12.5% stratified sampling patch as the candidate experiment for a clean review branch only after a separate apply step. Before promotion, rerun one more full seed or a medium-cost repeat to check whether the MAE regression is stable or seed-specific.

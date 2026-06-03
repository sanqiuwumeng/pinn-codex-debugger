# Rules-MCP Frozen Benchmark Replay

## Scope

- Branch: `exp/rules-mcp`
- Frozen prompt suite: `validation/blind-tests/2026-06-02_nine-family-baseline/prompts.jsonl`
- Handbook SHA256: `C7D3DD557F7942D6E10FE4331162297C07AF68AFFEC165066BC21CF8CE48EF16`
- Runtime dependencies: Python standard library only

## Deterministic Retrieval Results

| Case | Expected family | Actual family | Match | Top handbook section |
| --- | --- | --- | --- | --- |
| `boundary-condition-failure` | boundary handling | boundary handling | Yes | `第十章 硬约束、距离函数与边界条件处理` |
| `late-time-divergence` | temporal propagation | temporal propagation | Yes | `第十六章 Causal PINN、时间分段与课程学习` |
| `local-residual-hotspot` | localized sampling difficulty | localized sampling difficulty | Yes | `第十二章 自适应采样、RAR、RAD 与残差点更新` |
| `high-frequency-smoothing` | high-frequency representation | high-frequency representation | Yes | `第十三章 Fourier Features、SIREN与多尺度表达` |
| `inverse-parameter-drift` | inverse identifiability | inverse identifiability | Yes | `第二十三章 反问题、参数约束、贝叶斯PINN 与不确定性` |
| `conservation-drift` | physical structure preservation | physical structure preservation | Yes | `第二十一章 守恒约束、结构保持与物理量监控` |
| `high-order-pde-instability` | high-order autodiff cost | high-order autodiff cost | Yes | `第十九章 FO-PINN、VPINN、弱形式方法与 Deep Ritz` |
| `repeated-parametric-solves` | operator learning task | operator learning task | Yes | `第二十四章 DeepONet、FNO、PINO与物理信息算子学习` |
| `underspecified-failure` | underspecified | underspecified | Yes | `第一章 遇到 PINN 问题时先查这张表` |

Family routing accuracy: `9 / 9`.

## Comparison With Skill-Only

- `skill-only` blind response score: `86 / 90` (`95.6%`).
- `rules-mcp` deterministic family routing: `9 / 9`.
- `rules-mcp` returns source hash, heading, matched anchors, and line range for each evidence match.
- This replay measures deterministic retrieval structure. It does not replace isolated response-quality blind testing.

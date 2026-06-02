# Skill-Only Baseline Results

## Scope

This is the installed skill-only baseline evaluation. It validates skill structure, handbook provenance, keyword routing, a manual rubric dry run, and isolated Codex App implicit-trigger behavior. The personal Skill installation matches the repo-owned Skill byte-for-byte.

## Provenance

| Item | Value |
| --- | --- |
| Source handbook | `PINN报错诊断与模块选择手册.md` |
| Packaged handbook | `references/PINN报错诊断与模块选择手册.md` |
| Source SHA256 | `C7D3DD557F7942D6E10FE4331162297C07AF68AFFEC165066BC21CF8CE48EF16` |
| Packaged SHA256 | `C7D3DD557F7942D6E10FE4331162297C07AF68AFFEC165066BC21CF8CE48EF16` |
| Hash match | Yes |

## Structural Validation

| Check | Result |
| --- | --- |
| Codex skill validator | Pass |
| Evaluation fixture parse | Pass |
| Fixture count | 9 |
| Required symptom coverage | Pass |
| Keyword-routable cases | 9 / 9 |
| Zero-match final anchors | 0 |
| Personal skill installation | Performed; repo-owned and personal Skill files match |
| Isolated auto-trigger blind test | Pass: `3 / 3` boundary-focused threads |
| Conda package changes | None |
| MCP configuration changes | None |

## Installed Skill Verification

The personal Skill at `C:\Users\Mli\.codex\skills\pinn-debugging-assistant` matches the repo-owned `skills/pinn-debugging-assistant` directory file-by-file after synchronization.

## Isolated Auto-Trigger Blind Test

The first isolated Codex App blind-test run is archived outside the portable Skill at:

```text
validation/blind-tests/2026-06-02_boundary-auto-trigger/
```

| Case | Scenario | Auto-triggered | Single next experiment | Result |
| --- | --- | --- | --- | --- |
| `01` | 1D Poisson endpoint error | Yes | Yes | Pass with minor deviation |
| `02` | Heat equation initial and boundary error | Yes | Yes | Pass with minor deviation |
| `03` | 2D rectangle edge and corner error | Yes | Yes | Pass with minor deviation |

All three responses prioritized boundary or initial-condition expressions, constraint-point coverage, and component losses before architecture changes. The next benchmark expands isolated coverage to all nine symptom families.

## Manual Rubric Dry Run

The manual pass applies the response contract from `SKILL.md` to each fixture and verifies that the routing index leads to one next experiment, a metric, rollback guidance, and a handbook anchor.

| Case | Symptom family | Next single change | Expected metric | Rollback condition | Handbook anchor | Score |
| --- | --- | --- | --- | --- | --- | ---: |
| `boundary-condition-failure` | boundary handling | test a hard boundary constraint after expression and point checks | boundary-error curve | revert if boundary error does not improve or interior error worsens | `第十章 硬约束、距离函数与边界条件处理` | 10 / 10 |
| `late-time-divergence` | temporal propagation | test causal training | time-segment error | revert if late-time error does not improve or early-time accuracy regresses | `第十六章 Causal PINN、时间分段与课程学习` | 10 / 10 |
| `local-residual-hotspot` | localized sampling difficulty | test RAR | hotspot residual or local error | revert if the hotspot persists or global error worsens | `第十二章 自适应采样、RAR、RAD 与残差点更新` | 10 / 10 |
| `high-frequency-smoothing` | high-frequency representation | test Fourier Features | spectrum or phase error | revert if oscillation error does not improve or boundary oscillation appears | `第十三章 Fourier Features、SIREN与多尺度表达` | 10 / 10 |
| `inverse-parameter-drift` | inverse identifiability | test parameter reparameterization | parameter trajectory | revert if drift persists or state fit degrades | `第二十三章 反问题、参数约束、贝叶斯 PINN 与不确定性` | 10 / 10 |
| `conservation-drift` | physical structure preservation | test one conservation constraint | conservation-error curve | revert if drift does not improve or pointwise error becomes unacceptable | `第二十一章 守恒约束、结构保持与物理量监控` | 10 / 10 |
| `high-order-pde-instability` | high-order autodiff cost | test FO-PINN reformulation | training time and derivative stability | revert if runtime or stability does not improve | `第十九章 FO-PINN、VPINN、弱形式方法与 Deep Ritz` | 10 / 10 |
| `repeated-parametric-solves` | operator learning task | evaluate DeepONet as the first operator-learning baseline | cross-parameter generalization error | revert if amortized inference benefit does not justify training cost | `第二十四章 DeepONet、FNO、PINO 与物理信息算子学习` | 10 / 10 |
| `underspecified-failure` | underspecified | request per-term losses, plots, and configuration; recommend no module | none until evidence exists | remain at baseline until the symptom is observable | `附录 E 训练现场总检查卡`, `检查卡 1:症状是否明确` | 10 / 10 |

Manual rubric score: `90 / 90`.

## Known Retrieval Weaknesses

1. The first operator-learning anchor used `多组参数`, but the converted handbook's exact quick-reference phrase is `多参数重复求解`. Keyword routing required a synonym-oriented index correction.
2. Generic anchors such as `硬约束`, `RAR`, and `DeepONet` appear in many locations. Plain `rg` retrieves relevant text but does not rank the best section automatically.
3. Some Markdown tables were converted into long inline HTML rows. Keyword matching works, but extracting a clean, narrow evidence block can be noisy.
4. The first blind Codex App pass validates boundary-focused auto-trigger behavior only. The remaining symptom families still require isolated blind coverage.

## Comparison Targets

Use the same fixtures and rubric in later branches.

- `rules-mcp`: measure whether structured symptom records improve precision and evidence extraction.
- `hybrid-rag`: measure whether semantic retrieval handles paraphrases without hand-maintained synonym expansion.

# Case 02: Late-Time Divergence

## Metadata

- Case ID: `late-time-divergence`
- Thread ID: `019e8798-681d-7923-9a5d-cbd541f6755d`
- Date: `2026-06-02`
- Prompt: `我在训练一个瞬态问题。模型在开始的一小段时间预测还可以，但越往后偏差越明显，最后完全失真。请帮我安排排查顺序和下一步实验。`

## Raw Response

老大，当前只能做初步诊断：这是典型的“短时间可用、后期误差累积并失真”。先不要加深网络，也不要直接换 LSTM。

**Symptom**
初值附近预测尚可，但误差随时间持续放大，最终崩溃。

**Evidence**
先固定同一个 seed 和 baseline，补齐以下记录：

- 将时间域等分为 5 到 10 段，画每段 `relative L2 error` 或 RMSE。
- 分时间段统计 `PDE residual`，不要只看全局平均值。
- 记录 `IC loss`、`BC loss`、`PDE loss`、各项梯度范数。
- 画守恒量或关键物理量随时间的漂移曲线。
- 核对各时间段的残差点数量，确认后期没有采样稀疏。

**Basic checks**
按这个顺序排查：

1. 核对 PDE 符号、时间导数、变量维度和自动微分计算图。
2. 核对初值、边界条件表达式、mask 和采样位置。
3. 检查时间坐标、空间坐标、输出量和 residual 是否归一化或无量纲化。
4. 比较早期、中期、后期的残差点覆盖率和误差热力图。
5. 检查学习率、数值精度、优化器切换和不同 seed 的重复性。

**Next Experiments**
每次只改一个逻辑点，并保留 baseline：

| 顺序 | 实验 | 唯一改动 | 判断目的 |
|---|---|---|---|
| E0 | 基线复跑 | 不改模型，只补充分段指标 | 确认误差从哪个时间段开始增长 |
| E1 | 时间采样对照 | 各时间段使用相同数量的残差点 | 排除后期覆盖不足 |
| E2 | 短时间截断 | 仅训练最早 20% 时间域 | 验证早期解能否真正学稳 |
| E3 | 课程式扩展 | E2 收敛后逐段扩大时间窗口 | 首选改进实验 |
| E4 | `time-marching PINN` | 每个窗口以上一窗口末态作为下一窗口初值 | 若课程式训练仍不够稳定，再尝试 |
| E5 | `Causal PINN` 权重 | 对早期未收敛时间段提高优先级 | 若全域训练必须保留，再尝试 |

暂时不要把 E3、E4、E5 同时叠加，否则无法判断真正有效的是哪一项。

**Expected metric**
首要指标是“误差开始明显增长的时间点”向后移动。同步观察：

- 后期时间段 RMSE 或相对误差下降；
- 分段 residual 不再随时间持续抬升；
- 守恒量漂移减小；
- IC、BC 指标没有恶化。

**Rollback**
若某项实验只降低总 loss，却让边界误差、守恒漂移或后期误差恶化，立即撤回 baseline。若 E2 在短时间域内仍学不稳，先回到基础实现、尺度和优化器排查，不进入时间模块改造。

**Handbook anchor**
依据：`第一章` 的“初值满足但时间后期崩溃”、`第十六章 Causal PINN、时间分段与课程学习`，以及 `检查卡 8：时间问题是否考虑因果顺序`。

## Scoring Notes

| Criterion | Score | Notes |
| --- | ---: | --- |
| Symptom family | 2 | Correctly identifies temporal propagation failure. |
| Basic checks | 2 | Covers temporal evidence, implementation, scales, sampling, and optimization. |
| One-change discipline | 0 | Lists a staged matrix from `E0` to `E5` instead of one next experiment. |
| Metric and rollback | 2 | Defines time-segment metrics and rollback behavior. |
| Traceability | 2 | Cites the relevant temporal chapter and checklist. |
| Total | 8 | Minor contract deviation. |

## Retrieval Notes

- Anchors or sections: `第一章`, `第十六章`, `检查卡 8`
- Retrieval miss: no
- Manual synonym expansion: no
- Multi-module stacking: yes; staged options are listed even though simultaneous stacking is discouraged
- Missing rollback: no
- Missing handbook anchor: no
- Response-concision deviation: yes; returns a broad experiment matrix

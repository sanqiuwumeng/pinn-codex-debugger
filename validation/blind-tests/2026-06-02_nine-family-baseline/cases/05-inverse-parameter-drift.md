# Case 05: Inverse Parameter Drift

## Metadata

- Case ID: `inverse-parameter-drift`
- Thread ID: `019e8798-799f-7461-a37d-8cd7c35ca10e`
- Date: `2026-06-02`
- Prompt: `我的反演任务中，状态量曲线已经拟合得不错，但待识别参数在训练过程中来回漂移，最后结果也超出合理范围。请给出诊断顺序。`

## Raw Response

老大，状态量拟合良好但参数持续漂移，优先怀疑“弱可辨识性”，不是网络容量不足。不同参数组合可能产生近似相同的状态曲线。

**Symptom:**  
状态误差较低，但待识别参数震荡、跨越物理合理范围，最终值不稳定。

**Evidence:**  
先补齐最小证据：

1. 每个参数的 epoch 轨迹和允许范围。
2. `PDE loss`、`data loss`、`BC loss`、`IC loss` 分项曲线。
3. 各分项 loss 对每个待识别参数的梯度范数。
4. 不同随机种子的最终参数分布。
5. 按时间段、空间区域和观测变量拆分的状态误差。

**Basic checks:**  
按以下顺序逐级排查：

1. **方程与自动微分**  
   核对参数进入 PDE 的位置、符号、单位和导数实现。确认没有漏乘尺度因子。

2. **参数尺度**  
   将待识别参数无量纲化到相近量级。检查状态量、坐标和 PDE residual 是否也已缩放。  
   参数跨数量级时，优化器很容易沿“平坦方向”漂移。

3. **可辨识性**  
   在合理参数范围内做局部扫描：每次只扰动一个参数，观察预测状态和 residual 是否明显变化。  
   再检查多个参数同时变化时，是否存在相互补偿。可计算敏感度矩阵  
   \[
   S_{ij}=\frac{\partial u(x_i,t_i)}{\partial \theta_j}
   \]
   如果某列接近零，或不同列高度相关，对应参数无法由现有观测稳定识别。

4. **观测覆盖**  
   检查观测变量、位置和时间窗口。增加数据点未必有效；关键是增加对目标参数敏感区域的数据。时间依赖问题要分别看早期、中期和后期。

5. **多目标竞争**  
   比较各分项 loss 对参数的梯度。如果 `data loss` 已很低，但参数梯度长期由某一项主导或互相抵消，检查权重与 residual 尺度。

6. **优化稳定性**  
   检查参数学习率是否过大。网络权重和物理参数最好使用独立学习率，并记录 Adam 与 L-BFGS 切换前后的参数轨迹。

7. **噪声与重复性**  
   至少运行 3 个随机种子。若状态曲线相近而参数结果离散，基本可以确认是可辨识性或噪声问题。

**Next single change:**  
先不要叠加新模块。做一次“参数敏感度扫描”，固定当前网络结构、采样和损失权重，仅在合理范围内扰动待识别参数，定位不可辨识参数和补偿关系。

**Expected metric:**  
关注敏感度矩阵的列范数、列间相关性或条件数，以及不同 seed 下参数终值的方差。状态误差只能作为辅助指标。

**Rollback:**  
保留当前 baseline。若扫描显示参数本身可辨识，再单独尝试参数重参数化，例如  
\[
\theta=\theta_{\min}+(\theta_{\max}-\theta_{\min})\operatorname{sigmoid}(z)
\]
以施加物理范围约束。若扫描显示不可辨识，单纯加约束只能阻止越界，不能恢复真实参数，应调整观测设计或报告不确定区间。

**Handbook anchor:**  
`PINN报错诊断与模块选择手册.md`：`反问题、参数约束、贝叶斯 PINN 与不确定性`、`诊断卡 9——与反问题的关系`、`检查卡 9:反问题是否可辨识`。

## Scoring Notes

| Criterion | Score | Notes |
| --- | ---: | --- |
| Symptom family | 2 | Correctly identifies inverse identifiability. |
| Basic checks | 2 | Covers parameters, scales, observations, sensitivity, losses, and seeds. |
| One-change discipline | 2 | Recommends one parameter-sensitivity scan. |
| Metric and rollback | 2 | Defines sensitivity and seed-variance metrics plus rollback. |
| Traceability | 2 | Cites relevant inverse-problem anchors. |
| Total | 10 | Pass. |

## Retrieval Notes

- Anchors or sections: `反问题、参数约束、贝叶斯 PINN 与不确定性`, `诊断卡 9`, `检查卡 9`
- Retrieval miss: no
- Manual synonym expansion: no
- Multi-module stacking: no
- Missing rollback: no
- Missing handbook anchor: no
- Response-concision deviation: minor; setup commentary mentioned sandbox handling

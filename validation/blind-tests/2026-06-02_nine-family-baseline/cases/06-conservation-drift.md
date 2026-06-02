# Case 06: Conservation Drift

## Metadata

- Case ID: `conservation-drift`
- Thread ID: `019e8798-8024-79b3-bcef-fcafe440eacf`
- Date: `2026-06-02`
- Prompt: `预测场在采样点上的相对误差不大，但计算出来的总质量会随着时间持续偏移。请告诉我最先要补哪些证据，以及下一步只做什么改动。`

## Raw Response

老大，使用 `pinn-debugging-assistant`：先按“守恒量随时间漂移”路径定位，不先换网络结构。

**Symptom:**  
采样点相对误差较小，但积分总质量持续偏移。这说明点值拟合尚可，模型没有充分保持全局守恒结构。

**Evidence:**  
最先补 4 组曲线，使用与 baseline 完全相同的时间切片：

1. 总质量曲线  
   \[
   M(t)=\int_\Omega \rho(x,t)\,d\Omega,\qquad
   \delta_M(t)=\frac{M(t)-M(0)}{M(0)}
   \]

2. 质量平衡缺口  
   对封闭系统：
   \[
   R_M(t)=\frac{dM}{dt}
   \]
   对开放边界：
   \[
   R_M(t)=\frac{dM}{dt}+\int_{\partial\Omega} \rho u\cdot n\,dS
   \]

3. PDE residual 的时间分段统计和热力图：早期、中期、后期分别记录均值、最大值和高分位数。不要只看采样点平均值。

4. 边界通量误差曲线：同时核查法向量方向、入口出口符号、积分权重和边界采样覆盖。

**Basic checks:**  
先确认连续性方程符号、归一化后的量纲、自动微分变量、数值积分权重，以及 `PDE / BC / IC / data` 分项 loss。若质量偏移主要来自通量符号或积分实现错误，先修这个基础错误，不加模块。

**Next single change:**  
如果基础检查无误，只新增一个全局质量平衡损失，不同时改采样、网络、优化器或其他权重策略：

\[
L_{\mathrm{mass}}
=
\frac{1}{N_t}\sum_k R_M(t_k)^2
\]

保留原 baseline，先固定一个小而明确的 `lambda_mass` 做单因素消融。封闭域使用 `dM/dt`；开放域必须包含边界通量项。

**Expected metric:**  
首要指标是 `max_t |\delta_M(t)|` 和 `RMS(R_M)` 明显下降；同时确认原有相对误差和 BC loss 没有明显恶化。

**Rollback:**  
若质量漂移没有下降，或相对误差、边界误差明显变差，就撤回该损失，检查积分实现和新增项与其他 loss 的量级、梯度范数。

**Handbook anchor:**  
`第四章 从预测图、残差图和物理量曲线判断病因`、`检查卡 10:物理量是否监控`、`检查卡 11:模块是否有消融依据`。

## Scoring Notes

| Criterion | Score | Notes |
| --- | ---: | --- |
| Symptom family | 2 | Correctly identifies physical structure preservation. |
| Basic checks | 2 | Covers mass, flux, residual, integration, scale, and loss evidence. |
| One-change discipline | 2 | Recommends one mass-balance loss. |
| Metric and rollback | 2 | Defines conservation metrics and rollback. |
| Traceability | 2 | Cites relevant physical-quantity anchors. |
| Total | 10 | Pass. |

## Retrieval Notes

- Anchors or sections: `第四章`, `检查卡 10`, `检查卡 11`
- Retrieval miss: no
- Manual synonym expansion: no
- Multi-module stacking: no
- Missing rollback: no
- Missing handbook anchor: no
- Response-concision deviation: minor; setup commentary mentioned sandbox handling

# Case 07: High-Order PDE Instability

## Metadata

- Case ID: `high-order-pde-instability`
- Thread ID: `019e8799-9d69-74f3-bee8-30ba60f859c3`
- Initial failed thread ID: `019e8798-85b2-7001-9d0c-9ca850fedef3`
- Date: `2026-06-02`
- Prompt: `我处理的方程需要四阶导数，训练很慢，显存占用高，而且损失曲线抖动明显。继续增加内部点是否值得？请给出诊断和下一步。`

## Raw Response

老大，结论：**暂时不值得继续均匀增加内部点**。四阶自动微分会显著放大计算图、显存和梯度噪声；继续加点通常同时恶化三个现象。只有 residual 热力图显示明确局部热点时，才值得做局部加点或 RAR。

**Symptom:**  
四阶 PDE 的直接强形式 PINN 训练慢、显存高、loss 抖动，优先怀疑高阶自动微分成本和数值稳定性，而不是点数不足。

**Evidence:**  
已有证据：导数阶数为 4，且出现耗时、显存、震荡三联症。  
还需补齐：`PDE/BC/IC` 分项 loss、各项梯度范数、residual 热力图、单步耗时、峰值显存、精度 `float32/float64`、学习率。

**Basic checks:**  
1. 确认四阶导数来自正确变量，计算图未断开。  
2. 检查输入、输出和 PDE residual 是否无量纲化。  
3. 检查震荡是否与过大学习率或 `float32` 有关。  
4. 查看 residual 是否局部集中。没有局部热点时，不增加内部点。

**Next single change:**  
保留当前点数和网络，先做一次固定 seed 的 baseline 诊断运行，仅补充上述日志和 residual 热力图。不要同时改采样、网络或权重。

根据结果再决定：  
- residual 局部热点明显：优先局部加点或 RAR，不做全域均匀加点。  
- residual 普遍抖动且显存成本高：下一轮优先尝试将四阶方程改写为一阶系统的 `FO-PINN`。这是架构改动，实际实施前需要您回复 `Yes`。  
- `float32` 明显不稳定：单独比较 `float64`，但要预期显存进一步增加。

**Expected metric:**  
先获得可解释 baseline；后续改动应降低 loss 波动幅度，并比较单步耗时、峰值显存、验证误差和 residual 热点。

**Rollback:**  
任何方案若显存或单步耗时明显上升，但验证误差和稳定性没有同步改善，就撤回当前 baseline。

**Handbook anchor:**  
`高阶 PDE 训练很慢或不稳定`、`D.10 FO-PINN、VPINN、弱形式方法与 Deep Ritz`、`检查卡 3:残差分布是否查看`、`检查卡 6:采样是否覆盖困难区域`。

## Infrastructure Note

The initial isolated thread `019e8798-85b2-7001-9d0c-9ca850fedef3` ended with `systemError` and no assistant response. The retry used the exact same blind prompt and no added context.

## Scoring Notes

| Criterion | Score | Notes |
| --- | ---: | --- |
| Symptom family | 2 | Correctly identifies high-order autodiff cost and instability. |
| Basic checks | 2 | Covers derivative graph, scales, precision, learning rate, residual distribution, and runtime evidence. |
| One-change discipline | 2 | Recommends one diagnostic baseline run before architecture changes. |
| Metric and rollback | 2 | Defines runtime, memory, stability, and error metrics plus rollback. |
| Traceability | 2 | Cites relevant high-order and sampling anchors. |
| Total | 10 | Pass after one infrastructure retry. |

## Retrieval Notes

- Anchors or sections: `高阶 PDE 训练很慢或不稳定`, `D.10`, `检查卡 3`, `检查卡 6`
- Retrieval miss: no
- Manual synonym expansion: no
- Multi-module stacking: no
- Missing rollback: no
- Missing handbook anchor: no
- Response-concision deviation: minor; setup commentary mentioned sandbox handling

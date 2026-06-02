# Case 08: Repeated Parametric Solves

## Metadata

- Case ID: `repeated-parametric-solves`
- Thread ID: `019e8798-8b4d-7c90-b765-34444a34cef9`
- Date: `2026-06-02`
- Prompt: `我需要对大量不同参数组合快速得到结果，但现在每换一组参数都要重新训练一次，成本太高。请判断问题本质，并给一个优先实验。`

## Raw Response

老大，使用 `pinn-debugging-assistant`：这不是单次 PINN 精度问题，而是任务定义需要升级。

**Symptom:**  
每组参数都训练一个独立 PINN，离线成本随参数组合数量近似线性增长，无法支撑批量快速预测。

**Evidence:**  
已知需求是跨参数组合重复求解。还需记录：参数维数、取值范围、单次训练耗时、单次推理耗时，以及是否改变几何、边界函数或初值函数。

**Basic checks:**  
先确认当前单参数 baseline 正确：方程符号、边界与初值、参数尺度归一化、分项 loss、独立数值解误差。否则共享模型只会批量复现错误。

**问题本质:**  
当前网络学习的是单个解 `u(x,t)`。真正需要学习的是参数化解映射：

```text
(x, t, μ) -> u(x, t; μ)
```

也就是把成本从“每组参数重新优化”改为“离线训练一次，在线快速推理”。低维标量参数变化时，先做条件化 parametric PINN；输入函数、几何或高维场变化时，再考虑 DeepONet、FNO 或 PINO。

**Next single change:**  
做一个最小条件化 PINN 实验：仅将归一化参数向量 `μ` 拼接到原 PINN 输入中，网络、损失形式和优化器保持不变。  
在参数空间内取少量覆盖点训练，并保留未参与训练的插值测试点；先不要同时引入 DeepONet、FNO 或额外模块。

**Expected metric:**  
同时比较：

- 未见参数上的相对 `L2` 误差和 PDE residual；
- 单组新参数的在线推理耗时；
- 总摊销成本：`一次共享训练成本 / 原单参数训练成本`。

若 held-out 参数误差可接受，且推理从“重新训练”降为一次前向传播，就证明路线成立。

**Rollback:**  
若训练参数点拟合良好，但插值测试点明显失真，先回退并检查参数空间覆盖与归一化。不要直接堆更复杂架构。外推参数应单独评估，不能用插值结果替代。

**Handbook anchor:**  
`routing-index.md` 的 `Many parameter sets require repeated solves`；手册 `D.15 DeepONet、FNO、PINO 与物理信息算子学习`，锚点为“任务需要跨参数、跨初值或跨输入函数反复快速预测”。

## Scoring Notes

| Criterion | Score | Notes |
| --- | ---: | --- |
| Symptom family | 2 | Correctly identifies an operator-learning task boundary. |
| Basic checks | 2 | Preserves validation of the single-parameter baseline. |
| One-change discipline | 2 | Recommends one minimal conditional-PINN experiment. |
| Metric and rollback | 2 | Defines held-out accuracy, inference cost, amortized cost, and rollback. |
| Traceability | 2 | Cites the routing index and operator-learning diagnostic card. |
| Total | 10 | Pass. |

## Retrieval Notes

- Anchors or sections: `Many parameter sets require repeated solves`, `D.15`
- Retrieval miss: no
- Manual synonym expansion: no
- Multi-module stacking: no
- Missing rollback: no
- Missing handbook anchor: no
- Response-concision deviation: no

# Case 01: Boundary Condition Failure

## Metadata

- Case ID: `boundary-condition-failure`
- Thread ID: `019e8798-61ec-7b73-9ffb-1059de2326d7`
- Date: `2026-06-02`
- Prompt: `我的 PINN 内域误差已经降下来，但边界附近始终偏差很大，边界点上的误差曲线也不稳定。请判断最应该先排查什么，并给出下一步实验。`

## Raw Response

老大，当前最应该先排查的不是网络容量，而是**边界约束是否被正确施加**。

**Symptom:**  
内域误差已下降，但边界附近持续偏差大，且边界点误差曲线震荡。这首先指向边界表达式、边界采样或边界 loss 与 PDE loss 的竞争问题。

**Evidence:**  
已有证据：内域可以学到，边界表现明显更差。  
最小缺失证据：分别记录每一段边界的 `BC loss`、最大绝对误差、边界点坐标，以及 `BC loss / PDE loss` 的量级比。

**Basic checks:**  
先逐项核对：

1. 边界点是否真的落在几何边界上，角点是否重复或漏采。
2. Dirichlet 条件的目标值是否正确。
3. Neumann 条件是否对正确变量求导，外法向方向是否一致。
4. 边界 `mask` 是否错选、漏选，或混入内域点。
5. 输入归一化后，边界坐标和导数尺度是否同步转换。
6. 各边界分项 loss 是否被平均方式或权重压得过小。

**Next single change:**  
先不要加硬约束、RAR 或新网络。做一个边界审计实验：保持模型、优化器、采样数量和权重完全不变，只把每段边界拆开记录并可视化。每隔固定步数输出：

```text
BC_left, BC_right, BC_top, BC_bottom
max_abs_error_per_boundary
boundary_point_coordinates
PDE_loss
```

若包含 Neumann 条件，再额外输出预测法向导数、目标法向导数和法向量。

**Expected metric:**  
应能定位到某一段边界异常：其误差明显更高、震荡更强，或坐标、法向、目标值不符合定义。只有审计全部通过后，下一轮才值得单独测试“边界加密采样”。

**Rollback:**  
本实验只增加日志和图，不改变 baseline。若各边界均正确且量级正常，再恢复原日志配置，并进入边界重采样实验。

**Handbook anchor:**  
`PINN报错诊断与模块选择手册.md`：`第十章 硬约束、距离函数与边界条件处理`、`检查卡 4: 边界和初值是否单独验证`、`检查卡 6: 采样是否覆盖困难区域`。

## Scoring Notes

| Criterion | Score | Notes |
| --- | ---: | --- |
| Symptom family | 2 | Correctly prioritizes boundary handling. |
| Basic checks | 2 | Covers expressions, points, masks, normals, scales, and component losses. |
| One-change discipline | 2 | Recommends one boundary-audit experiment. |
| Metric and rollback | 2 | Defines localization evidence and a baseline-preserving rollback. |
| Traceability | 2 | Cites relevant handbook anchors. |
| Total | 10 | Pass. |

## Retrieval Notes

- Anchors or sections: `第十章`, `检查卡 4`, `检查卡 6`
- Retrieval miss: no
- Manual synonym expansion: no
- Multi-module stacking: no
- Missing rollback: no
- Missing handbook anchor: no
- Response-concision deviation: minor; setup commentary mentioned sandbox handling

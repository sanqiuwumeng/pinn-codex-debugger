# PINN Debugging Routing Index

Use this file as navigation guidance. Treat the full handbook as the source of detailed claims.

## Mandatory Order

1. Write one observable symptom.
2. Save or inspect baseline evidence.
3. Complete relevant basic checks.
4. Introduce one logical change only.
5. Compare at least one training-process metric and one result-quality metric.
6. Revert if the expected metric does not improve or a new risk appears.

## Basic Check Anchors

| Check family | Search anchors |
| --- | --- |
| Equation and autodiff | `第六章`, `公式`, `变量`, `维度`, `自动微分`, `导数` |
| Scaling | `第七章`, `归一化`, `非维化`, `尺度` |
| Training flow | `第八章`, `优化器`, `学习率`, `精度`, `训练流程` |
| Evidence and reproducibility | `第九章`, `指标`, `日志`, `可复现`, `baseline` |

## Symptom Routing

| Observable symptom | Search anchors | First evidence | Candidate family after basic checks |
| --- | --- | --- | --- |
| Boundary conditions remain violated | `边界条件`, `BC loss`, `硬约束`, `距离函数`, `边界重采样` | boundary-error curve, boundary points, boundary expression | hard constraint or boundary handling |
| Initial condition holds but late time diverges | `初值满足但时间后期崩溃`, `后期时间`, `Causal PINN`, `time-marching`, `时间分段` | time-segment error, early-time error, time sampling | causal training or time marching |
| Error or residual is concentrated locally | `局部区域误差特别大`, `局部尖峰错`, `RAR`, `RAD`, `残差点更新` | residual heatmap, local gradient, boundary-layer location | adaptive sampling |
| Solution is over-smoothed or loses high frequency | `解被过度抹平`, `高频消失`, `Fourier Features`, `SIREN`, `多尺度表达` | frequency content, phase error, input scale | frequency features |
| High-order PDE training is slow or unstable | `高阶 PDE`, `FO-PINN`, `VPINN`, `弱形式`, `Deep Ritz` | derivative order, graph cost, precision, residual scale | first-order or weak-form methods |
| Inverse parameters drift | `反问题参数乱飘`, `不可辨识`, `贝叶斯 PINN`, `参数重参数化` | parameter trajectory, sensitivity, data coverage, noise | parameter constraints or uncertainty modeling |
| Conservation quantity drifts | `守恒量随时间漂移`, `守恒约束`, `结构保持`, `物理量监控` | mass, energy, momentum, flux, divergence curve | conservation-aware constraint |
| One network cannot fit the whole domain | `一个网络学不完整个区域`, `XPINN`, `cPINN`, `FBPINN`, `域分解` | regional error, interface location, subdomain behavior | domain decomposition |
| Many parameter sets require repeated solves | `多参数重复求解`, `DeepONet`, `FNO`, `PINO`, `算子学习` | parameter space, function inputs, data coverage | operator learning |
| Result is not reproducible | `结果不可复现`, `固定 seed`, `日志规范`, `多随机种子` | seeds, initialization, sample batches, run statistics | reproducibility fixes before modules |

## High-Value Handbook Sections

| Purpose | Heading or anchor |
| --- | --- |
| Fast symptom lookup | `第一章 遇到 PINN 问题时先查这张表` |
| Common diagnostic language | `第二章 PINN 调试的基础语言` |
| Loss interpretation | `第三章 从 loss 曲线判断病因` |
| Plot and physical-quantity interpretation | `第四章 从预测图、残差图和物理量曲线判断病因` |
| Baseline discipline | `第五章 最小可复现 PINN 与 baseline思维` |
| Symptom-module quick reference | `附录 A 症状-模块速查表` |
| Training-site final checks | `附录 E 训练现场总检查卡` |

## Search Examples

```powershell
rg -n "第一章|边界条件|BC loss|硬约束|距离函数" "references/PINN报错诊断与模块选择手册.md"
rg -n "后期时间|Causal PINN|time-marching|时间分段" "references/PINN报错诊断与模块选择手册.md"
rg -n "局部区域|残差热力图|RAR|RAD|自适应采样" "references/PINN报错诊断与模块选择手册.md"
rg -n "高频|Fourier Features|SIREN|多尺度" "references/PINN报错诊断与模块选择手册.md"
rg -n "反问题|参数乱飘|不可辨识|贝叶斯 PINN" "references/PINN报错诊断与模块选择手册.md"
```

## Required Response Shape

```text
Symptom:
Evidence:
Basic checks:
Next single change:
Expected metric:
Rollback:
Handbook anchor:
```

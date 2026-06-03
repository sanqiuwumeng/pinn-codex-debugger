# Hybrid-RAG Subagent Output

- Agent ID: `019e8b26-dc7e-7690-b47e-0051f2e43999`
- Scheme: `hybrid-rag`

## Raw Output

老大，Scheme: hybrid-rag

## 1. Symptom
PINN-2D 的主症状不是边界条件失效，而是 `t=5.0` 早期相变/液相区域误差最突出：relative L2 达 `0.11869`，melted-area relative error 为 `0.4667`，liquid-mask IoU 只有 `0.6818`，且最大温度误差 `279.465 K` 出现在该时间片。

## 2. Evidence used
已验证硬约束通过：top、initial、bottom/left/right Neumann 误差均为 `0` 或数值零量级。

全场误差：relative L2 `5.824683e-02`，MAE `12.2297 K`，max abs error `279.465 K`。

最差时间片为 `t=5.0`：预测液相面积比 `0.0015026`，参考液相面积比 `0.0010245`，说明液相面积被高估。

hybrid-rag 检索 top-ranked section 指向“硬约束、距离函数与边界条件处理”，但该方向与已验证硬约束事实冲突，应视为由 query 中 `top/initial/Neumann constraints` 触发的边界词检索偏置。

重新排序后，更相关的是“检查卡 6: 采样是否覆盖困难区域”和“本章目标”中关于 relative L2、残差图、物理量监控不能只看边界/总损失的原则。

## 3. Evidence not used or missing
未使用源码、模型权重、图像文件或训练日志；本轮不运行实验。

缺少 per-term loss、PDE residual heatmap、相界面附近误差热图、采样点分布、loss 权重、`pinn_loss_stability.png` 的具体曲线读数。

缺少确认误差峰值是否集中在液相线/固相线区间 `1878-1928 K` 附近的空间证据。

## 4. Basic checks
边界/初值检查：已通过，不应作为当前主因。

方程/物性一致性检查：case packet 显示 PINN 与 FEM 使用相同简化相变模型，zero-latent PINN/FEM reduction 均通过，因此不是优先怀疑项。

尺度与局部残差检查：仍缺少相变区 PDE residual 与温度误差的空间对应关系。

采样覆盖检查：应优先审计 `t=5.0` 附近、热源中心附近、液相线/固相线附近的 collocation 或评估覆盖是否不足。

## 5. Next single diagnostic step
只做诊断：把下一步证据审计聚焦到 `t=5.0` 的相变界面区域，检查温度误差、液相 mask 差异、PDE residual 和采样覆盖是否共同集中在熔池边界/潜热区间附近。

这一步不是改模型、不是重训，而是确认 dominant failure mode 是否为早期相变界面区域的局部解析/采样不足。

## 6. Expected metric movement
如果该诊断成立，后续针对性修正应首先改善 `t=5.0` melted-area relative error、liquid-mask IoU 和该时间片 relative L2；全场 relative L2 可能小幅改善，但不是最敏感指标。

## 7. Rollback or falsification condition
若 `t=5.0` 的误差、残差和采样稀疏并不集中在相变界面/热源中心附近，或液相面积高估无法由局部界面偏移解释，则否定“局部相变区覆盖不足”为主因，回退到检查 PDE residual 尺度、潜热有效热容项、时间早期权重或优化稳定性证据。

## 8. Handbook anchor
主要锚点：`检查卡 6:采样是否覆盖困难区域`。

辅助锚点：`本章目标`，尤其是“PDE residual 不是最终误差”、relative L2 需要参照解、应补充物理量监控和残差图。

被降权锚点：`第十章 硬约束、距离函数与边界条件处理`，原因是 case packet 已验证 hard top/initial/Neumann constraints 通过。

## 9. Do-not-modify confirmation
本轮仅基于 case packet、output contract 和 retrieval-records 的 `hybrid_rag` 记录进行只读诊断；未修改文件、未改模型、未重训、未写入任何输出文件。

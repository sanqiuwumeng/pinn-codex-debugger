# Case 02: Heat Equation Initial and Boundary Error

## Thread

`019e876e-8ff0-78e0-b506-ef7c17ee485b`

## Blind Prompt

> 我的热方程 PINN 训练不稳定：内部配点上的 residual 看起来还可以，但靠近初始时刻和空间边缘时预测明显不对。网络、优化器和采样策略都有可能有问题。请告诉我应该先检查什么，以及下一步实验。

## Auto-trigger Evidence

> 老大，我会用 `pinn-debugging-assistant` 技能先按热方程的物理约束拆解问题。

## Final Response

> 老大，先不要改网络深度或优化器。这个症状更像是 IC/BC 约束、尺度或采样覆盖问题，而不是内域 residual 不够低。
>
> **Symptom:**  
> 内部训练点 residual 尚可，但 `t≈0`、`x≈x_left`、`x≈x_right` 附近误差明显偏大。采样点上的低 residual 不能证明边缘区域正确。
>
> **Evidence:**  
> 先保存当前 baseline，并补齐 4 张图：
> 1. `PDE loss`、`IC loss`、`BC loss` 分项曲线。
> 2. 独立密集网格上的 residual 热力图，不使用训练点。
> 3. `t=0` 的误差曲线，以及多个时间切片上的边界误差。
> 4. 每个 loss 项的梯度范数，以及三次固定 seed 的结果。
>
> **Basic checks:**  
> 按此顺序检查：
> 1. 热方程是否确实写成 `r = u_t - α u_xx`，符号、变量和二阶自动微分链路是否正确。
> 2. 若归一化了 `x,t`，确认 `u_t` 和 `u_xx` 已乘回正确的链式法则系数。
> 3. IC 点是否严格满足 `t=0`；BC 点是否严格位于空间边缘；Neumann 边界还要核对法向。
> 4. 单独检查角点 `(x_left,0)` 和 `(x_right,0)`：IC 与 BC 是否一致。
> 5. 统计早期时间带和边缘带中的点数，例如 `t/T<0.1`、距边界不足 `0.05L` 的区域。
> 6. 若训练点上的 `IC loss` 或 `BC loss` 仍偏大，先处理表达式、尺度或梯度失衡，不要立即上 RAR。
>
> **Next single change:**  
> 如果基础检查通过，首轮实验只改采样策略：保持网络、优化器、学习率、loss 权重和总配点数不变，将一部分内域配点重分配到 `t≈0` 与空间边缘附近的分层区域。不要同时加入 RAR、自适应权重或更深网络。
>
> **Expected metric:**  
> 早期时间带和边缘带上的 held-out RMSE 应明显下降，同时全域 relative L2 error 不恶化。还要观察 IC/BC 最大误差，而不只看平均 residual。
>
> **Rollback:**  
> 若边缘 RMSE 没有改善，或内域误差明显变差，恢复 baseline。下一轮再依据梯度范数判断是否单独调整 IC/BC 权重。

## Evaluation

- Auto-trigger: pass
- Boundary expression, boundary points, and BC loss weight considered: pass
- Exactly one next experiment: pass
- Minor deviation: it requests several plots before reducing the first interaction to the desired three-item check


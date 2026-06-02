# Case 01: 1D Poisson Endpoint Error

## Thread

`019e876e-89de-7fa2-b224-de1c627d93ac`

## Blind Prompt

> 我在调一个 1D Poisson 方程的 PINN。训练后 PDE residual 已经明显下降，但预测解整体有偏移，在区间两端误差尤其大。请帮我判断最值得先排查什么，并给出下一步怎么做。

## Auto-trigger Evidence

> 老大，我会先按 `pinn-debugging-assistant` 的诊断流程抓主因。

## Final Response

> 老大，使用 `pinn-debugging-assistant` 后，最值得先查的是边界条件，而不是继续压低 PDE residual。
>
> **Symptom:**  
> PDE residual 已下降，但预测解整体偏移，端点误差最大。
>
> **Evidence:**  
> 对 1D Poisson 方程 `u''(x)=f(x)`，仅降低 residual 不能排除齐次解 `ax+b`。  
> - 两端误差接近同号、同幅：优先怀疑常数偏移 `b`。  
> - 两端误差呈线性变化或异号：优先怀疑斜率项 `ax`。
>
> 这通常说明 Dirichlet 边界没有被正确施加，或 `BC loss` 被 PDE loss 压制。
>
> **Basic checks:**  
> 1. 单独打印 `u(a)`、`u(b)`、目标边界值和左右端点误差。  
> 2. 确认边界采样点真的落在 `x=a`、`x=b`，mask 没有写反。  
> 3. 单独画 `PDE loss` 与 `BC loss`，不要只看总 loss。  
> 4. 用解析解代入 residual 实现，检查 Poisson 方程正负号和二阶自动微分是否正确。  
> 5. 检查输入归一化后，二阶导数是否乘回了正确尺度因子。
>
> **Next single change:**  
> 若边界表达式确认无误且是 Dirichlet 条件，下一轮只改为硬约束：
>
> ```text
> u_hat(x) = g(x) + (x-a)(b-x) * N_theta(x)
>
> g(x) = u(a) + (u(b)-u(a)) * (x-a)/(b-a)
> ```
>
> 保持网络、采样点、优化器、学习率和随机种子不变。
>
> **Expected metric:**  
> 左右端点绝对误差应接近数值精度，同时 relative `L2` error 明显下降；PDE residual 不应显著恶化。
>
> **Rollback:**  
> 若端点已经满足但内域仍偏移，或加入硬约束后 residual 明显变差，就回退 baseline，转而检查残差符号、归一化尺度和二阶导数实现。若是 Neumann 或混合边界，不要直接套用上述公式。

## Evaluation

- Auto-trigger: pass
- Boundary expression, boundary points, and BC loss weight considered: pass
- Exactly one next experiment: pass
- Minor deviation: the initial checklist is broader than the requested three-item first check


# Case 03: 2D Rectangle Edge and Corner Error

## Thread

`019e876e-9580-7231-bb1e-46b1b35091a7`

## Blind Prompt

> 我有一个二维矩形域上的 PINN，内部残差已经降到比较低，但边缘附近的预测仍然失真，角点最明显。我不确定该先调网络结构、增加采样、改 loss，还是检查实现。请帮我按优先级诊断。

## Auto-trigger Evidence

> 老大，我会使用 `pinn-debugging-assistant` 技能，先按手册把“实现错误、约束冲突、采样盲区、优化权重、网络容量”分层排序。

## Final Response

> 老大，当前诊断是暂定的：最可疑的是边界约束实现或边界覆盖不足，网络结构排在最后。内部采样点上的 residual 很低，不能证明边缘正确。
>
> **Symptom:**  
> 二维矩形域内误差较小，但误差向边缘集中，角点最严重。
>
> **Evidence:**  
> 已有证据：内部 residual 已下降。  
> 下一步最少需要保存：
>
> - 四条边分别计算 `BC error`
> - 四个角点单独计算误差
> - 边界附近窄带的误差与 residual 热力图
> - `PDE loss`、各边 `BC loss`、各项梯度范数
> - 边界采样点散点图与每条边点数
>
> **Basic checks:**  
> 按以下优先级排查：
>
> 1. **检查实现**
>    - 边界点是否严格落在 `x=xmin/xmax`、`y=ymin/ymax`
>    - 四条边的 mask 是否正确，角点是否被遗漏或重复计权
>    - 相邻边在角点处的 Dirichlet 值是否相容
>    - Neumann 边界的法向符号是否正确；角点法向是否被误用
>    - 自动微分变量、导数阶数、PDE 符号和归一化是否正确
>
> 2. **检查采样覆盖**
>    - 角点附近是否几乎没有边界点
>    - 内部采样是否避开了靠边窄带
>    - residual 均值是否掩盖了局部热点
>
> 3. **检查 loss**
>    - 比较 `PDE loss` 与每条边的 `BC loss`
>    - 比较梯度范数，判断 PDE 项是否压制 BC 项
>    - 只有确认尺度合理后，才调整 BC 权重或使用自适应权重
>
> 4. **考虑硬约束**
>    - 若边界表达式明确且无噪声，可考虑 `u(x,y) = g(x,y) + d(x,y) Nθ(x,y)`
>    - 矩形域可构造在边界为零的距离函数 `d`
>    - 若相邻边在角点不相容，不要强行硬约束
>
> 5. **最后才改网络**
>    - 仅当边界实现、覆盖和权重都正常，而窄边界层仍被过度平滑时，再考虑 Fourier Features、SIREN 或多尺度网络。
>
> **Next single change:**  
> 先保持网络、优化器和 loss 权重不变，只重新分配边界采样：增加四个角点邻域和靠边窄带采样，并单独记录每条边及角点误差。不要同时改权重。
>
> **Expected metric:**  
> 角点最大误差、边界 `L∞ error` 和窄带误差应下降；内部 residual 不应明显恶化。
>
> **Rollback:**  
> 保留当前 seed、配置和 checkpoint。若边界误差没有下降，或内部误差显著上升，撤回采样改动，转去检查 mask、角点相容性和分项梯度范数。

## Evaluation

- Auto-trigger: pass
- Boundary expression, boundary points, and BC loss weight considered: pass
- Exactly one next experiment: pass
- Minor deviation: it names deferred modules such as hard constraints, Fourier Features, and SIREN, which slightly disperses the first response


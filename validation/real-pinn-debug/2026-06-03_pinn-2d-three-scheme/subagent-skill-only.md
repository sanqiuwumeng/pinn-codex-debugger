# Skill-Only Subagent Output

- Agent ID: `019e8b26-7c5a-7ad3-9fa5-22b90c864736`
- Scheme: `skill-only`

## Raw Output

老大，Scheme: skill-only

1. Symptom

t=5.0 是主异常切片：全局误差不算失控，但早期熔化区被明显高估，melted-area relative error = 0.4667，liquid-mask IoU = 0.6818，max abs error = 279.465 K。

2. Evidence used

使用了 case packet 中的只读指标：硬约束全部通过，FEM 网格收敛通过，零潜热 PINN/FEM reduction 通过。全场 relative L2 = 5.824683e-02，MAE = 12.2297 K。最差切片为 t=5.0，relative L2 = 0.11869，MAE = 22.8026 K，预测液相面积比 0.0015026，高于参考 0.0010245。

3. Evidence not used or missing

未使用 rules-mcp、hybrid-rag 检索记录、源码修改、模型权重、重训结果。缺少最关键的现有诊断证据：t=5.0 的 PDE residual 分布、相变温区 1878-1928 K 附近采样覆盖、分项 loss 曲线、残差尺度/归一化量级、collocation 点在早期熔池附近的密度。

4. Basic checks

基础检查结论：边界/初值不是当前第一嫌疑，因为 top、initial、bottom/left/right Neumann hard constraints 已接近零误差；参考解可靠性也有 FEM grid convergence 和 zero-latent reduction 支撑。仍需优先确认 PDE 符号、潜热有效热容项、温度输出尺度、PDE residual 归一化、以及 t=5.0 熔池附近 residual/采样分布，而不是先改网络或加训练轮数。

5. Next single diagnostic step

只做一个逻辑点：用已有输出和日志定位 t=5.0 熔化界面附近的局部误差、residual 热点和采样覆盖是否重合，重点看 1878-1928 K 相变带及中央加热下方区域。若三者重合，主因应判为“早期相变局部区域采样/残差约束覆盖不足或尺度失衡”，下一轮才考虑单独处理采样覆盖；本轮不改模型、不重训。

6. Expected metric movement

若该诊断成立，最先应改善的不是全场 L2，而是 t=5.0 的 melted-area relative error 下降、liquid-mask IoU 上升、phase/interface 局部误差缩小；max abs error 也应在早期熔池附近下降。

7. Rollback or falsification condition

若现有 residual/误差图显示 t=5.0 的误差不集中在相变带或熔池局部，或采样覆盖已经充分且分项 residual 尺度均衡，则否定“局部采样覆盖”为主因，回退到方程符号、潜热项尺度、自动微分变量和归一化审计。

8. Handbook anchor

`routing-index.md`: “Error or residual is concentrated locally” 路由，基础检查锚点为 equation/autodiff、scaling、evidence。`PINN报错诊断与模块选择手册.md`: 第一章“局部区域误差特别大”；第四章“局部区域错误大，优先怀疑采样不足或局部结构难学”；第六章“公式、变量、维度与自动微分排查”；第七章“归一化、非维化与尺度问题”；第十二章“自适应采样、RAR、RAD 与残差点更新”；附录 E“检查卡 6: 采样是否覆盖困难区域”。

9. Do-not-modify confirmation

已按只读诊断执行：未修改任何文件、未写入输出、未改源码、未改模型权重、未启动重训、未使用 rules-mcp 或 hybrid-rag 检索记录。

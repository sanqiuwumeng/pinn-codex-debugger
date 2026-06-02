# Case 04: High-Frequency Smoothing

## Metadata

- Case ID: `high-frequency-smoothing`
- Thread ID: `019e8798-7376-7b20-bf33-3410a86532e6`
- Date: `2026-06-02`
- Prompt: `真实解里有持续振荡和很窄的峰，但我训练出的曲线明显更平滑，峰值和相位都对不上。请判断先查什么，再建议一个实验。`

## Raw Response

老大，使用 `pinn-debugging-assistant` 手册诊断。

**Symptom:**  
真实解含持续高频振荡和窄峰；预测被过度平滑，同时存在峰值衰减与相位偏差。

**Evidence:**  
现有描述支持两种可能：局部采样未覆盖窄峰，或普通 MLP 存在高频表达不足。还缺三张图：稠密验证网格上的误差、PDE residual 热力图、真实解与预测解的频谱对比。

**Basic checks:**  
先核对方程符号、自动微分、归一化和各分项 loss。随后优先查采样覆盖：窄峰附近是否有足够 residual 点，局部 residual 是否形成热点。不要用较低的平均 residual 判断模型已经正确。

**Next single change:**  
保持网络、优化器、损失权重和总采样点数不变，只做一次 RAR 实验：从稠密候选点中选取高 residual 点，替换一部分原有均匀采样点，同时保留全局均匀点。这样可以单独检验是否主要受限于局部采样。

**Expected metric:**  
首先应看到窄峰邻域的最大绝对误差和局部 residual 峰值下降；同时记录峰值幅度误差、峰位置误差和相位误差。若窄峰改善但持续振荡仍偏平滑，下一轮才有依据单独测试 Fourier Features 或 SIREN。

**Rollback:**  
若局部误差没有稳定改善，或全局误差、BC/IC loss 明显恶化，则撤回 RAR，回到 baseline，再查高频表达能力。

**Handbook anchor:**  
`第十二章 自适应采样、RAR、RAD 与残差点更新`、`检查卡 6: 采样是否覆盖困难区域`、`第十三章 Fourier Features、SIREN 与多尺度表达`。

## Scoring Notes

| Criterion | Score | Notes |
| --- | ---: | --- |
| Symptom family | 2 | Identifies high-frequency smoothing and separates a cheaper sampling hypothesis. |
| Basic checks | 2 | Requests residual, spectrum, scale, and loss evidence. |
| One-change discipline | 2 | Recommends one RAR experiment before architecture changes. |
| Metric and rollback | 2 | Defines local peak and phase metrics plus rollback. |
| Traceability | 2 | Cites sampling and high-frequency chapters. |
| Total | 10 | Pass. |

## Retrieval Notes

- Anchors or sections: `第十二章`, `检查卡 6`, `第十三章`
- Retrieval miss: no
- Manual synonym expansion: no
- Multi-module stacking: no
- Missing rollback: no
- Missing handbook anchor: no
- Response-concision deviation: minor; setup commentary mentioned sandbox handling

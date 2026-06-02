# Case 03: Local Residual Hotspot

## Metadata

- Case ID: `local-residual-hotspot`
- Thread ID: `019e8798-6d8b-7553-be7c-cd44221b8c81`
- Date: `2026-06-02`
- Prompt: `全域平均误差看起来还能接受，但误差图里有一个很小的区域一直特别亮。把总采样点数均匀加倍后改善不明显。下一步应该怎么查？`

## Raw Response

老大，已使用 `pinn-debugging-assistant` 手册定位。下一步不要继续均匀加点，先判断亮斑究竟是“局部漏采样”还是“边界、尺度或表达能力问题”。

**Symptom:**  
全域平均误差可接受，但同一小区域持续出现高误差；均匀加倍采样点收益很弱。优先怀疑局部困难区域覆盖不足。

**Evidence:**  
已有证据：误差热点稳定存在、全域均匀加点改善不明显。  
最小补充证据：

1. 在相同坐标系叠加 `误差热力图`、`PDE residual 热力图` 和 `现有残差点分布`。
2. 标记热点是否贴近边界、尖峰、激波、材料界面或几何角点。
3. 用至少 2 个随机种子确认热点是否反复出现在同一区域。
4. 单独记录热点区域的 `max error`、`P95 error` 和 `max |residual|`，不要只看全域均值。

**Basic checks:**  
先确认方程符号、自动微分、边界条件、热点附近法向或 mask、归一化和各项 loss 尺度没有错误。尤其注意：误差热点与 residual 热点不一定重合。若误差亮但 residual 不亮，应优先查边界传播、参考解质量或网络表达能力，而不是直接加点。

**Next single change:**  
基础检查通过后，只做一个单变量实验：保留当前总采样点数不变，将一部分均匀点改为基于 residual 的自适应重采样，例如 RAR。候选池中优先补入高 residual 点，同时保留足够的全域均匀点，避免模型只盯着局部。

**Expected metric:**  
热点区域的 `P95 error`、面积占比和 `max |residual|` 应下降；全域误差、边界误差和训练稳定性不应恶化。

**Rollback:**  
若热点位置频繁漂移、局部指标没有稳定改善，或边界误差明显上升，撤回 RAR。下一轮再单独判断是否属于高频或尖峰表达不足，届时才考虑 Fourier Features、SIREN 或域分解。

**Handbook anchor:**  
`第十二章 自适应采样、RAR、RAD 与残差点更新`，以及 `检查卡 3：残差分布是否查看`、`检查卡 6：采样是否覆盖困难区域`。

## Scoring Notes

| Criterion | Score | Notes |
| --- | ---: | --- |
| Symptom family | 2 | Correctly identifies localized sampling difficulty. |
| Basic checks | 2 | Distinguishes residual hotspots from other local-error causes. |
| One-change discipline | 2 | Recommends one adaptive-sampling experiment. |
| Metric and rollback | 2 | Defines local and global metrics plus rollback. |
| Traceability | 2 | Cites relevant handbook anchors. |
| Total | 10 | Pass. |

## Retrieval Notes

- Anchors or sections: `第十二章`, `检查卡 3`, `检查卡 6`
- Retrieval miss: no
- Manual synonym expansion: no
- Multi-module stacking: no
- Missing rollback: no
- Missing handbook anchor: no
- Response-concision deviation: minor; setup commentary asked about sandbox handling

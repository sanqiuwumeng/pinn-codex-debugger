# Case 09: Underspecified Failure

## Metadata

- Case ID: `underspecified-failure`
- Thread ID: `019e8798-9268-7992-830f-4e37c3a99ba4`
- Date: `2026-06-02`
- Prompt: `我的 PINN 效果不理想。请直接帮我挑一个更先进的改进方法。`

## Raw Response

老大，当前信息不足，不能可靠地挑“更先进”的方法。只知道效果差，直接上 PirateNets、XPINN 或 Causal PINN 很可能掩盖基础问题。

**Symptom:** 仅能确认 PINN 整体效果不理想，具体失败模式未知。  
**Evidence:** 请提供代码，以及 `PDE loss / BC loss / IC loss / data loss` 曲线、预测误差图、残差热力图；时变问题再提供分时间段误差。  
**Basic checks:** 我会先核对 PDE 符号与自动微分、边初值、归一化、采样覆盖、损失尺度和优化器。  
**Next single change:** 暂不指定模块。若基础检查通过且残差明显集中在局部区域，我优先选 `RAR` 残差自适应采样：改动小、可独立消融，通常比直接换网络结构更稳妥。  
**Expected metric:** 局部峰值误差和验证网格上的残差高分位数下降。  
**Rollback:** 指标无改善，或边界误差、守恒误差恶化，就恢复 baseline。  
**Handbook anchor:** `第一章 遇到 PINN 问题时先查这张表`、`第十二章 自适应采样、RAR、RAD 与残差点更新`。

另外，请确认是否为这次任务创建并使用 conda 沙箱。

## Scoring Notes

| Criterion | Score | Notes |
| --- | ---: | --- |
| Symptom family | 2 | Correctly identifies insufficient evidence. |
| Basic checks | 2 | Requests concrete code, losses, plots, residuals, and time slices. |
| One-change discipline | 0 | The underspecified-case contract requires no module recommendation, but the answer prematurely names conditional `RAR`. |
| Metric and rollback | 2 | Defines provisional metric and rollback. |
| Traceability | 2 | Cites relevant anchors. |
| Total | 8 | Conservative refusal is present, but the conditional module mention is premature. |

## Retrieval Notes

- Anchors or sections: `第一章`, `第十二章`
- Retrieval miss: no
- Manual synonym expansion: no
- Multi-module stacking: no
- Missing rollback: no
- Missing handbook anchor: no
- Response-concision deviation: yes; conditional module suggestion and sandbox question should be omitted

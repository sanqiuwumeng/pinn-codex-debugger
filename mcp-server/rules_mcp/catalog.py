"""Rule catalog for deterministic PINN symptom routing."""

from __future__ import annotations

from .models import SymptomRule


def build_rules() -> tuple[SymptomRule, ...]:
    """Return the immutable symptom routing catalog."""
    return (
        SymptomRule(
            rule_id="boundary-condition-failure",
            family="boundary handling",
            keywords=("边界", "边缘", "端点", "角点", "bc loss", "法向"),
            required_basic_checks=(
                "boundary expression",
                "boundary points or mask",
                "boundary weight",
                "boundary normal if relevant",
            ),
            evidence_gaps=(
                "boundary-error curve",
                "boundary-point coordinates",
                "per-boundary loss components",
            ),
            candidate_anchors=(
                "第十章 硬约束、距离函数与边界条件处理",
                "检查卡 4:边界和初值是否单独验证",
                "检查卡 6:采样是否覆盖困难区域",
            ),
        ),
        SymptomRule(
            rule_id="late-time-divergence",
            family="temporal propagation",
            keywords=("瞬态", "越往后", "后期", "时间段", "发散", "最终失真"),
            required_basic_checks=(
                "time scale",
                "time sampling",
                "time window",
                "early-time error",
            ),
            evidence_gaps=(
                "time-segment error",
                "time-segment residual",
                "early-time versus late-time sampling coverage",
            ),
            candidate_anchors=(
                "第十六章 Causal PINN、时间分段与课程学习",
                "检查卡 8:时间问题是否考虑因果顺序",
                "初值满足但时间后期崩溃",
            ),
        ),
        SymptomRule(
            rule_id="local-residual-hotspot",
            family="localized sampling difficulty",
            keywords=("局部", "小区域", "特别亮", "热点", "均匀加倍", "残差图"),
            required_basic_checks=(
                "residual heatmap",
                "local gradient",
                "boundary-layer location",
                "sampling coverage",
            ),
            evidence_gaps=(
                "residual heatmap",
                "local-error heatmap",
                "collocation-point distribution",
            ),
            candidate_anchors=(
                "第十二章 自适应采样、RAR、RAD 与残差点更新",
                "检查卡 3:残差分布是否查看",
                "检查卡 6:采样是否覆盖困难区域",
            ),
        ),
        SymptomRule(
            rule_id="high-frequency-smoothing",
            family="high-frequency representation",
            keywords=("振荡", "窄峰", "尖峰", "平滑", "相位", "高频", "峰值"),
            required_basic_checks=(
                "frequency content",
                "input scale",
                "verify spike is physical",
                "activation function",
            ),
            evidence_gaps=(
                "frequency spectrum",
                "phase error",
                "peak-location error",
            ),
            candidate_anchors=(
                "第十三章 Fourier Features、SIREN与多尺度表达",
                "检查卡 7:网络表达是否匹配解的形态",
                "解被过度抹平",
            ),
        ),
        SymptomRule(
            rule_id="inverse-parameter-drift",
            family="inverse identifiability",
            keywords=("反演", "反问题", "待识别参数", "参数乱飘", "参数", "漂移", "合理范围"),
            required_basic_checks=(
                "parameter range",
                "sensitivity",
                "observed variables",
                "noise level",
            ),
            evidence_gaps=(
                "parameter trajectory",
                "parameter sensitivity",
                "observational coverage",
            ),
            candidate_anchors=(
                "第二十三章 反问题、参数约束、贝叶斯PINN 与不确定性",
                "检查卡 9:反问题是否可辨识",
                "反问题参数乱飘",
            ),
        ),
        SymptomRule(
            rule_id="conservation-drift",
            family="physical structure preservation",
            keywords=("总质量", "质量", "守恒", "通量", "随时间持续偏移", "物理量"),
            required_basic_checks=(
                "mass curve",
                "flux curve",
                "boundary flux",
                "residual distribution",
            ),
            evidence_gaps=(
                "conservation-error curve",
                "boundary-flux curve",
                "time-segment residual",
            ),
            candidate_anchors=(
                "第二十一章 守恒约束、结构保持与物理量监控",
                "检查卡 10:物理量是否监控",
                "守恒量随时间漂移",
            ),
        ),
        SymptomRule(
            rule_id="high-order-pde-instability",
            family="high-order autodiff cost",
            keywords=("四阶", "高阶", "显存", "导数", "计算图", "抖动"),
            required_basic_checks=(
                "derivative order",
                "computation graph",
                "precision",
                "residual scale",
            ),
            evidence_gaps=(
                "step time",
                "peak memory",
                "loss-component gradients",
                "precision setting",
            ),
            candidate_anchors=(
                "第十九章 FO-PINN、VPINN、弱形式方法与 Deep Ritz",
                "高阶 PDE 训练很慢或不稳定",
                "检查卡 3:残差分布是否查看",
            ),
        ),
        SymptomRule(
            rule_id="repeated-parametric-solves",
            family="operator learning task",
            keywords=("大量不同参数", "参数组合", "每换一组参数", "重新训练", "快速得到结果", "重复求解"),
            required_basic_checks=(
                "parameter space",
                "input functions",
                "training data coverage",
            ),
            evidence_gaps=(
                "parameter-space definition",
                "single-solve training cost",
                "held-out parameter evaluation plan",
            ),
            candidate_anchors=(
                "第二十四章 DeepONet、FNO、PINO与物理信息算子学习",
                "多参数重复求解",
                "DeepONet、FNO、PINO 与物理信息算子学习:诊断卡 1",
            ),
        ),
    )


def underspecified_rule() -> SymptomRule:
    """Return the conservative fallback used when evidence does not route."""
    return SymptomRule(
        rule_id="underspecified-failure",
        family="underspecified",
        keywords=(),
        required_basic_checks=(
            "request concrete symptom",
            "request per-term losses or plots",
            "request configuration",
        ),
        evidence_gaps=(
            "observable symptom",
            "per-term losses",
            "prediction or residual plots",
            "training configuration",
        ),
        candidate_anchors=(
            "检查卡 1:症状是否明确",
            "第一章 遇到 PINN 问题时先查这张表",
        ),
    )

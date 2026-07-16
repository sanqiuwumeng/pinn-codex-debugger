"""Frozen-family routing and determinism regression tests."""

from __future__ import annotations

import unittest

from rules_mcp.models import DiagnosisRequest

from .support import create_rules_service, expected_handbook_sha256


def frozen_cases() -> tuple[tuple[str, str, str], ...]:
    """Return the product's nine canonical diagnosis families."""
    return (
        (
            "boundary-condition-failure",
            "boundary handling",
            "我的 PINN 内域误差已经降下来，但边界附近始终偏差很大，边界点上的误差曲线也不稳定。",
        ),
        (
            "late-time-divergence",
            "temporal propagation",
            "瞬态问题开始的一小段时间预测还可以，但越往后偏差越明显，最后完全失真。",
        ),
        (
            "local-residual-hotspot",
            "localized sampling difficulty",
            "全域平均误差可以接受，但误差图里有一个很小的区域一直特别亮。",
        ),
        (
            "high-frequency-smoothing",
            "high-frequency representation",
            "真实解有持续振荡和很窄的峰，但训练曲线明显更平滑，峰值和相位都不对。",
        ),
        (
            "inverse-parameter-drift",
            "inverse identifiability",
            "反演状态量拟合不错，但待识别参数来回漂移，最终超出合理范围。",
        ),
        (
            "conservation-drift",
            "physical structure preservation",
            "预测场相对误差不大，但总质量会随着时间持续偏移。",
        ),
        (
            "high-order-pde-instability",
            "high-order autodiff cost",
            "方程需要四阶导数，训练很慢，显存占用高，而且损失曲线抖动明显。",
        ),
        (
            "repeated-parametric-solves",
            "operator learning task",
            "需要对大量不同参数组合快速求解，但每换一组参数都要重新训练。",
        ),
        (
            "underspecified-failure",
            "underspecified",
            "我的 PINN 效果不理想，请直接挑一个更先进的方法。",
        ),
    )


class RulesRetrievalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = create_rules_service()

    def test_routes_all_frozen_prompt_families(self) -> None:
        for case_id, expected_family, prompt in frozen_cases():
            with self.subTest(case=case_id):
                record = self.service.diagnose(DiagnosisRequest(symptom=prompt))
                self.assertEqual(record.family, expected_family)
                self.assertEqual(
                    record.handbook_sha256, expected_handbook_sha256()
                )
                self.assertTrue(record.handbook_matches)

    def test_repeated_requests_are_identical(self) -> None:
        request = DiagnosisRequest(
            symptom="内域残差下降，但边界点误差仍然很大。",
            evidence=("BC loss curve",),
            max_sections=3,
        )

        first = self.service.diagnose(request).to_dict()
        second = self.service.diagnose(request).to_dict()

        self.assertEqual(first, second)

    def test_vague_symptom_uses_conservative_fallback(self) -> None:
        record = self.service.diagnose(
            DiagnosisRequest(symptom="我的 PINN 效果不理想。")
        )

        self.assertEqual(record.family, "underspecified")
        self.assertIn("observable symptom", record.evidence_gaps)
        self.assertIn("request concrete symptom", record.required_basic_checks)


if __name__ == "__main__":
    unittest.main()

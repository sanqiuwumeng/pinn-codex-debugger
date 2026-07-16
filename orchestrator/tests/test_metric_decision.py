from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.assurance import MetricDecisionService  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    AggregationPolicy,
    ArtifactRef,
    DecisionStatus,
    MetricContract,
    MetricDirection,
    MetricEvidenceBasis,
    MetricRole,
    MetricRule,
    MetricValueSet,
)

SHA = "d" * 64


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://metrics/{name}",
        sha256=SHA,
    )


def values(subject: str, **metrics: float) -> MetricValueSet:
    return MetricValueSet(subject_id=subject, values=metrics)


class MetricDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MetricDecisionService()

    def test_missing_user_priority_blocks_optimization(self) -> None:
        readiness = self.service.preference_readiness(None)
        self.assertFalse(readiness.ready)

        decision = self.service.compare(
            decision_id="decision-missing",
            contract=None,
            baseline=values("baseline", rmse=10.0),
            candidate=values("candidate", rmse=9.0),
            observed_failure_mechanism="unknown",
        )
        self.assertEqual(decision.status, DecisionStatus.NEEDS_EVIDENCE)

    def test_rmse_improvement_cannot_override_max_abs_guardrail(self) -> None:
        contract = MetricContract(
            contract_id="rmse-with-max-guardrail",
            physical_model_authority_ref=artifact("model-authority"),
            reference_evidence_refs=(artifact("truth"),),
            metrics=(
                MetricRule(
                    name="rmse",
                    role=MetricRole.PRIMARY,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                ),
                MetricRule(
                    name="max_abs",
                    role=MetricRole.GUARDRAIL,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                    max_regression=0.0,
                    unit="K",
                ),
            ),
            primary_order=("rmse",),
            aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
        )
        decision = self.service.compare(
            decision_id="decision-guardrail",
            contract=contract,
            baseline=values("baseline", rmse=10.0, max_abs=20.0),
            candidate=values("candidate", rmse=8.0, max_abs=25.0),
            observed_failure_mechanism="localized late-time error",
        )
        self.assertEqual(decision.status, DecisionStatus.REJECT)
        self.assertTrue(any("guardrail max_abs" in item for item in decision.reasons))

    def test_hard_constraint_is_checked_before_primary_improvement(self) -> None:
        contract = MetricContract(
            contract_id="hard-first",
            physical_model_authority_ref=artifact("model-authority"),
            reference_evidence_refs=(artifact("truth"),),
            metrics=(
                MetricRule(
                    name="energy_balance_error",
                    role=MetricRole.HARD_CONSTRAINT,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.PHYSICAL_MODEL,
                    threshold=0.01,
                ),
                MetricRule(
                    name="rmse",
                    role=MetricRole.PRIMARY,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                ),
            ),
            primary_order=("rmse",),
            aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
        )
        decision = self.service.compare(
            decision_id="decision-hard",
            contract=contract,
            baseline=values("baseline", energy_balance_error=0.005, rmse=10.0),
            candidate=values("candidate", energy_balance_error=0.02, rmse=5.0),
            observed_failure_mechanism="candidate violates conservation",
        )
        self.assertEqual(decision.status, DecisionStatus.REJECT)
        self.assertIn("hard constraint", decision.reasons[0])

    def test_lexicographic_order_follows_user_priority(self) -> None:
        contract = MetricContract(
            contract_id="max-first",
            physical_model_authority_ref=artifact("model-authority"),
            reference_evidence_refs=(artifact("truth"),),
            metrics=(
                MetricRule(
                    name="max_abs",
                    role=MetricRole.PRIMARY,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                ),
                MetricRule(
                    name="rmse",
                    role=MetricRole.PRIMARY,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                ),
            ),
            primary_order=("max_abs", "rmse"),
            aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
        )
        decision = self.service.compare(
            decision_id="decision-order",
            contract=contract,
            baseline=values("baseline", max_abs=20.0, rmse=10.0),
            candidate=values("candidate", max_abs=19.0, rmse=11.0),
            observed_failure_mechanism="local maximum is the user's first priority",
        )
        self.assertEqual(decision.status, DecisionStatus.ACCEPT)
        self.assertIn("max_abs", decision.reasons[0])

    def test_pareto_policy_rejects_any_primary_regression(self) -> None:
        contract = MetricContract(
            contract_id="pareto",
            physical_model_authority_ref=artifact("model-authority"),
            reference_evidence_refs=(artifact("truth"),),
            metrics=(
                MetricRule(
                    name="rmse",
                    role=MetricRole.PRIMARY,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                ),
                MetricRule(
                    name="iou",
                    role=MetricRole.PRIMARY,
                    direction=MetricDirection.MAXIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                ),
            ),
            primary_order=("rmse", "iou"),
            aggregation_policy=AggregationPolicy.PARETO,
        )
        decision = self.service.compare(
            decision_id="decision-pareto",
            contract=contract,
            baseline=values("baseline", rmse=10.0, iou=0.8),
            candidate=values("candidate", rmse=8.0, iou=0.7),
            observed_failure_mechanism="phase overlap regressed",
        )
        self.assertEqual(decision.status, DecisionStatus.REJECT)
        self.assertIn("iou", decision.reasons[0])

    def test_missing_required_metric_requests_evidence(self) -> None:
        contract = MetricContract(
            contract_id="missing-value",
            physical_model_authority_ref=artifact("model-authority"),
            reference_evidence_refs=(artifact("truth"),),
            metrics=(
                MetricRule(
                    name="rmse",
                    role=MetricRole.PRIMARY,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                ),
                MetricRule(
                    name="max_abs",
                    role=MetricRole.GUARDRAIL,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                    max_regression=0.0,
                    unit="K",
                ),
            ),
            primary_order=("rmse",),
            aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
        )
        decision = self.service.compare(
            decision_id="decision-missing-value",
            contract=contract,
            baseline=values("baseline", rmse=10.0, max_abs=20.0),
            candidate=values("candidate", rmse=8.0),
            observed_failure_mechanism="incomplete candidate report",
        )
        self.assertEqual(decision.status, DecisionStatus.NEEDS_EVIDENCE)
        self.assertIn("max_abs", decision.reasons[0])

    def test_absolute_and_relative_mae_guardrails_are_both_enforced(self) -> None:
        contract = MetricContract(
            contract_id="thermal-case-confirmed-order",
            physical_model_authority_ref=artifact("model-authority"),
            reference_evidence_refs=(artifact("fem-test-reference"),),
            metrics=(
                MetricRule(
                    name="max_abs",
                    role=MetricRole.PRIMARY,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                    unit="K",
                ),
                MetricRule(
                    name="rmse",
                    role=MetricRole.PRIMARY,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                    unit="K",
                ),
                MetricRule(
                    name="mae",
                    role=MetricRole.GUARDRAIL,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                    max_regression=1.0,
                    max_relative_regression=0.10,
                    unit="K",
                ),
            ),
            primary_order=("max_abs", "rmse"),
            aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
        )

        accepted = self.service.compare(
            decision_id="thermal-case-pass",
            contract=contract,
            baseline=values("baseline", max_abs=279.0, rmse=25.0, mae=12.23),
            candidate=values("candidate", max_abs=122.0, rmse=21.0, mae=13.22),
            observed_failure_mechanism="localized reference-backed error",
        )
        rejected = self.service.compare(
            decision_id="thermal-case-fail",
            contract=contract,
            baseline=values("baseline", max_abs=279.0, rmse=25.0, mae=5.0),
            candidate=values("candidate", max_abs=122.0, rmse=21.0, mae=5.75),
            observed_failure_mechanism="relative MAE regression",
        )

        self.assertEqual(accepted.status, DecisionStatus.ACCEPT)
        self.assertEqual(rejected.status, DecisionStatus.REJECT)
        self.assertTrue(any("relatively" in item for item in rejected.reasons))


if __name__ == "__main__":
    unittest.main()

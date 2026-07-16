from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.assurance import ExperimentGovernanceService  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    ArtifactRef,
    AuditStatus,
    BudgetSpec,
    ExperimentDraft,
    InterventionChange,
)

SHA = "1" * 64


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://governance/{name}",
        sha256=SHA,
    )


def intervention(target: str, before: int, after: int) -> InterventionChange:
    return InterventionChange(
        target=target,
        before=before,
        after=after,
        rationale=f"change only {target}",
    )


def complete_draft() -> ExperimentDraft:
    return ExperimentDraft(
        experiment_id="experiment-1",
        project_id="project-1",
        observed_failure_mechanism="localized late-time maximum error",
        supporting_evidence_refs=(artifact("prediction-report"),),
        interventions=(intervention("sampling.roi_points", 1000, 1500),),
        unchanged_controls=("network", "optimizer", "loss weights"),
        expected_primary_metric_movement={"rmse": "decrease"},
        guardrail_limits={"max_abs": 0.0},
        smoke_budget=BudgetSpec(max_steps=10),
        full_budget=BudgetSpec(max_steps=1000),
        falsification_condition="RMSE fails to improve or max_abs regresses.",
        rollback_plan="Keep the baseline configuration and artifacts.",
        source_snapshot_ref=artifact("source-snapshot"),
        dataset_refs=(artifact("dataset"),),
        environment_ref=artifact("environment"),
        random_seed=42,
        baseline_run_ref=artifact("baseline-run"),
        metric_contract_ref=artifact("metric-contract"),
        output_root="artifact://runs/experiment-1",
        checkpoint_policy="write before launch and at intervals",
        expected_artifacts=("metrics.json", "run_status.json"),
    )


class ExperimentGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ExperimentGovernanceService()

    def test_missing_baseline_returns_needs_evidence(self) -> None:
        payload = complete_draft().model_dump(mode="json")
        payload["baseline_run_ref"] = None
        report = self.service.audit(
            report_id="missing-baseline",
            draft=ExperimentDraft.model_validate(payload),
        )
        self.assertEqual(report.status, AuditStatus.NEEDS_EVIDENCE)
        self.assertIn("baseline", report.missing_fields)
        self.assertIsNone(report.experiment_spec)

    def test_multiple_independent_changes_are_rejected(self) -> None:
        payload = complete_draft().model_dump(mode="json")
        payload["interventions"].extend(
            [
                intervention("network.width", 64, 128).model_dump(mode="json"),
                intervention("loss.pde_weight", 1, 10).model_dump(mode="json"),
            ]
        )
        report = self.service.audit(
            report_id="multiple-changes",
            draft=ExperimentDraft.model_validate(payload),
        )
        self.assertEqual(report.status, AuditStatus.REJECT)
        self.assertFalse(report.checks["single_intervention"])

    def test_complete_draft_materializes_one_governed_spec(self) -> None:
        report = self.service.audit(
            report_id="complete",
            draft=complete_draft(),
        )
        self.assertEqual(report.status, AuditStatus.PASS)
        self.assertTrue(all(report.checks.values()))
        self.assertIsNotNone(report.experiment_spec)
        self.assertEqual(
            report.experiment_spec.single_intervention.target,
            "sampling.roi_points",
        )
        self.assertEqual(report.experiment_spec.random_seed, 42)


if __name__ == "__main__":
    unittest.main()

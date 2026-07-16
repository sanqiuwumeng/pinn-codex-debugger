from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.assurance import RunValidationService  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    ArtifactRef,
    AuditStatus,
    DecisionRecord,
    DecisionStatus,
    MetricEvidenceBasis,
    ModelEvaluationReport,
    PhysicalAuditReport,
    ResultStatus,
    RunValidationInput,
)

SHA = "3" * 64


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://validation/{name}",
        sha256=SHA,
    )


def valid_input(*, produced=None, exit_code: int = 0) -> RunValidationInput:
    return RunValidationInput(
        run_id="run-1",
        process_exit_code=exit_code,
        physical_audit=PhysicalAuditReport(
            report_id="physical-1",
            unit_system_id="model-units",
            status=AuditStatus.PASS,
        ),
        model_evaluation=ModelEvaluationReport(
            report_id="evaluation-1",
            status=ResultStatus.VALID,
            physical_model_authority_ref=artifact("model-authority"),
            metric_values={"rmse": 1.0, "max_abs": 1.0},
            metric_bases={
                "rmse": MetricEvidenceBasis.REFERENCE_EVIDENCE,
                "max_abs": MetricEvidenceBasis.REFERENCE_EVIDENCE,
            },
            prediction_analysis_ref=artifact("prediction-analysis"),
            checks={"all": True},
        ),
        metric_decision=DecisionRecord(
            decision_id="decision-1",
            status=DecisionStatus.ACCEPT,
            observed_failure_mechanism="localized prediction error",
        ),
        required_artifacts=("metrics.json", "prediction.npy"),
        produced_artifacts=produced
        or {
            "metrics.json": artifact("metrics"),
            "prediction.npy": artifact("prediction"),
        },
        run_manifest_ref=artifact("run-manifest"),
        source_snapshot_ref=artifact("source-snapshot"),
        dataset_refs=(artifact("dataset"),),
        environment_ref=artifact("environment"),
        random_seed=42,
    )


class RunValidationTests(unittest.TestCase):
    def test_zero_exit_with_missing_artifact_is_still_invalid(self) -> None:
        report = RunValidationService().validate(
            report_id="missing-artifact",
            validation_input=valid_input(
                produced={"metrics.json": artifact("metrics")}
            ),
        )
        self.assertEqual(report.status, ResultStatus.INVALID)
        self.assertFalse(report.checks["required_artifacts"])
        self.assertTrue(any("prediction.npy" in item for item in report.findings))

    def test_all_scientific_and_provenance_gates_are_required(self) -> None:
        report = RunValidationService().validate(
            report_id="valid",
            validation_input=valid_input(),
        )
        self.assertEqual(report.status, ResultStatus.VALID)
        self.assertTrue(all(report.checks.values()))
        self.assertGreaterEqual(len(report.evidence_refs), 7)

    def test_nonzero_exit_is_invalid_even_with_complete_artifacts(self) -> None:
        report = RunValidationService().validate(
            report_id="failed-process",
            validation_input=valid_input(exit_code=1),
        )
        self.assertEqual(report.status, ResultStatus.INVALID)
        self.assertFalse(report.checks["process_exit"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.contracts import (  # noqa: E402
    ArtifactRef,
    ResultStatus,
)
from pinn_strategy_system.execution import (  # noqa: E402
    FieldData,
    PredictionAnalyzer,
)

SHA = "e" * 64
AXES = ("t", "x", "y", "channel")
COORDINATES = {
    "t": np.array([0.0, 1.0]),
    "x": np.array([0.0, 1.0, 2.0, 3.0]),
    "y": np.array([0.0, 1.0, 2.0, 3.0]),
    "channel": np.array(["temperature"]),
}


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://prediction/{name}",
        sha256=SHA,
    )


def field_data(
    name: str,
    values: np.ndarray,
    *,
    coordinates=COORDINATES,
    reference_identity: str = "truth-v1",
    unit: str = "K",
    context_fields=None,
) -> FieldData:
    return FieldData(
        values=values,
        artifact_ref=artifact(name),
        axes=AXES,
        coordinates=coordinates,
        reference_identity=reference_identity,
        unit=unit,
        coordinate_system="cartesian-mm-s",
        normalization="physical",
        context_fields=context_fields or {},
    )


class PredictionAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = PredictionAnalyzer()
        self.reference_values = np.full((2, 4, 4, 1), 300.0)

    def test_localizes_max_topk_connected_regions_time_and_context(self) -> None:
        prediction_values = self.reference_values.copy()
        prediction_values[0, 1, 1, 0] += 5.0
        prediction_values[0, 1, 2, 0] += 4.0
        prediction_values[1, 3, 3, 0] += 10.0
        shape = prediction_values.shape
        residual = np.zeros(shape)
        residual[1, 3, 3, 0] = 2.5
        bc_ic = np.full(shape, "interior", dtype=object)
        density = np.full(shape, 32.0)
        region = np.full(shape, "solid", dtype=object)
        region[1, 3, 3, 0] = "mushy"
        roi = np.zeros(shape, dtype=bool)
        roi[1, :, :, :] = True

        report = self.analyzer.analyze(
            report_id="localized",
            prediction=field_data(
                "prediction",
                prediction_values,
                context_fields={
                    "pde_residual": residual,
                    "bc_ic_status": bc_ic,
                    "sampling_density": density,
                    "physical_region": region,
                },
            ),
            reference=field_data("truth", self.reference_values),
            top_k=3,
            connected_percentile=80.0,
            roi_masks={"late_time": roi},
        )

        self.assertEqual(report.status, ResultStatus.VALID)
        self.assertEqual(report.global_metrics["max_abs"], 10.0)
        self.assertEqual(report.max_abs.coordinates["t"], 1.0)
        self.assertEqual(report.max_abs.coordinates["x"], 3.0)
        self.assertEqual(report.max_abs.coordinates["y"], 3.0)
        self.assertEqual(report.max_abs.coordinates["channel"], "temperature")
        self.assertEqual(report.max_abs.prediction, 310.0)
        self.assertEqual(report.max_abs.reference, 300.0)
        self.assertEqual(report.max_abs.signed_error, 10.0)
        self.assertEqual(report.max_abs.context["pde_residual"], 2.5)
        self.assertEqual(report.max_abs.context["bc_ic_status"], "interior")
        self.assertEqual(report.max_abs.context["sampling_density"], 32.0)
        self.assertEqual(report.max_abs.context["physical_region"], "mushy")
        self.assertEqual(len(report.top_k), 3)
        self.assertEqual(len(report.connected_regions), 2)
        self.assertTrue(
            any(region.point_count == 2 for region in report.connected_regions)
        )
        self.assertEqual(len(report.time_slices), 2)
        self.assertEqual(report.time_slices[1].max_location["x"], 3.0)
        self.assertEqual(report.roi_metrics["late_time"]["max_abs"], 10.0)
        self.assertIn("p95", report.percentile_errors)

    def test_mismatched_time_grid_returns_invalid_report(self) -> None:
        mismatched = dict(COORDINATES)
        mismatched["t"] = np.array([0.0, 2.0])
        report = self.analyzer.analyze(
            report_id="misaligned",
            prediction=field_data("prediction", self.reference_values.copy()),
            reference=field_data(
                "truth",
                self.reference_values,
                coordinates=mismatched,
            ),
        )
        self.assertEqual(report.status, ResultStatus.INVALID)
        self.assertFalse(report.alignment_checks["coordinates"])
        self.assertIsNone(report.max_abs)

    def test_nan_prediction_returns_invalid_report(self) -> None:
        prediction_values = self.reference_values.copy()
        prediction_values[0, 0, 0, 0] = np.nan
        report = self.analyzer.analyze(
            report_id="nan",
            prediction=field_data("prediction", prediction_values),
            reference=field_data("truth", self.reference_values),
        )
        self.assertEqual(report.status, ResultStatus.INVALID)
        self.assertFalse(report.alignment_checks["finite_values"])

    def test_comparison_flags_migrated_comparable_maximum(self) -> None:
        baseline_values = self.reference_values.copy()
        baseline_values[0, 0, 0, 0] += 10.0
        candidate_values = self.reference_values.copy()
        candidate_values[0, 0, 0, 0] += 5.0
        candidate_values[1, 3, 3, 0] += 9.0

        comparison = self.analyzer.compare(
            report_id="migration",
            baseline=field_data("baseline", baseline_values),
            candidate=field_data("candidate", candidate_values),
            reference=field_data("truth", self.reference_values),
            top_k=2,
        )

        self.assertEqual(comparison.status, ResultStatus.VALID)
        self.assertTrue(comparison.error_migrated)
        self.assertEqual(
            comparison.baseline_report.max_abs.coordinates["x"],
            0.0,
        )
        self.assertEqual(
            comparison.candidate_report.max_abs.coordinates["x"],
            3.0,
        )
        self.assertLess(comparison.metric_deltas["max_abs"], 0)
        self.assertTrue(comparison.findings)

    def test_comparison_rejects_different_reference_identity(self) -> None:
        comparison = self.analyzer.compare(
            report_id="different-truth",
            baseline=field_data(
                "baseline",
                self.reference_values.copy(),
                reference_identity="truth-v1",
            ),
            candidate=field_data(
                "candidate",
                self.reference_values.copy(),
                reference_identity="truth-v2",
            ),
            reference=field_data(
                "truth",
                self.reference_values,
                reference_identity="truth-v1",
            ),
        )
        self.assertEqual(comparison.status, ResultStatus.INVALID)
        self.assertFalse(
            comparison.candidate_report.alignment_checks["reference_identity"]
        )


if __name__ == "__main__":
    unittest.main()

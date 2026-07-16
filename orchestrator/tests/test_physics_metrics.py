from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.contracts import ArtifactRef, ResultStatus  # noqa: E402
from pinn_strategy_system.domain_metrics import DomainProviderRegistry  # noqa: E402
from pinn_strategy_system.domain_metrics.heat_transfer import (  # noqa: E402
    HeatTransferPhaseConfig,
    HeatTransferPhaseMetricProvider,
)
from pinn_strategy_system.domain_metrics.residual import (  # noqa: E402
    ResidualMetricProvider,
)
from pinn_strategy_system.execution import (  # noqa: E402
    FieldData,
    PredictionAnalyzer,
)

SHA = "f" * 64


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://physics/{name}",
        sha256=SHA,
    )


def field(
    name: str,
    values: np.ndarray,
    *,
    channel: str = "temperature",
    unit: str = "K",
    context=None,
) -> FieldData:
    return FieldData(
        values=values,
        artifact_ref=artifact(name),
        axes=("t", "x", "y", "channel"),
        coordinates={
            "t": np.array([0.0]),
            "x": np.array([0.0, 1.0, 2.0, 3.0]),
            "y": np.array([0.0]),
            "channel": np.array([channel]),
        },
        reference_identity="phase-truth",
        unit=unit,
        coordinate_system="cartesian-mm-s",
        normalization="physical",
        context_fields=context or {},
    )


class PhysicsMetricTests(unittest.TestCase):
    def test_provider_registry_enables_only_case_selected_domains(self) -> None:
        heat = HeatTransferPhaseMetricProvider(
            HeatTransferPhaseConfig(
                solidus=1605.0,
                liquidus=1700.0,
                threshold_band=10.0,
            )
        )
        residual = ResidualMetricProvider(channel_name="u")
        registry = DomainProviderRegistry((heat, residual))

        selected = registry.select(("pinn.residual.v1",))

        self.assertEqual(registry.available_ids, (heat.provider_id, residual.provider_id))
        self.assertEqual(tuple(item.provider_id for item in selected), (residual.provider_id,))

    def test_phase_iou_geometry_threshold_and_residual_metrics(self) -> None:
        reference = np.array([[[[1600.0]], [[1650.0]], [[1750.0]], [[1800.0]]]])
        prediction = np.array([[[[1610.0]], [[1650.0]], [[1690.0]], [[1800.0]]]])
        residual = np.array([[[[1.0]], [[2.0]], [[3.0]], [[4.0]]]])
        sampling = np.full(reference.shape, 32.0)
        violations = np.array([[[[False]], [[False]], [[True]], [[False]]]])

        report = PredictionAnalyzer().analyze(
            report_id="phase-metrics",
            prediction=field(
                "prediction",
                prediction,
                context={
                    "pde_residual": residual,
                    "sampling_density": sampling,
                    "bc_ic_violation": violations,
                },
            ),
            reference=field("reference", reference),
            domain_metric_providers=(
                HeatTransferPhaseMetricProvider(
                    HeatTransferPhaseConfig(
                        solidus=1605.0,
                        liquidus=1700.0,
                        threshold_band=10.0,
                    )
                ),
                ResidualMetricProvider(channel_name="temperature"),
            ),
        )

        metrics = report.domain_metrics
        self.assertEqual(report.status, ResultStatus.VALID)
        self.assertEqual(metrics["phase_accuracy"], 0.5)
        self.assertEqual(metrics["liquid_mask_iou"], 0.5)
        self.assertAlmostEqual(metrics["mushy_mask_iou"], 1.0 / 3.0)
        self.assertEqual(metrics["solid_mask_iou"], 0.0)
        self.assertEqual(metrics["liquid_fraction_abs_error"], 0.25)
        self.assertEqual(metrics["liquid_extent_x_mae"], 1.0)
        self.assertEqual(metrics["phase_threshold_band_mae"], 10.0)
        self.assertEqual(metrics["pde_residual_mean_abs"], 2.5)
        self.assertTrue(
            math.isclose(metrics["pde_residual_rms"], math.sqrt(7.5))
        )
        self.assertEqual(metrics["pde_residual_max_abs"], 4.0)
        self.assertEqual(metrics["bc_ic_violation_fraction"], 0.25)
        self.assertEqual(metrics["sampling_density_phase_band_mean"], 32.0)

    def test_missing_configured_temperature_channel_invalidates_report(self) -> None:
        values = np.full((1, 4, 1, 1), 300.0)
        report = PredictionAnalyzer().analyze(
            report_id="wrong-channel",
            prediction=field("prediction", values, channel="u"),
            reference=field("reference", values, channel="u"),
            domain_metric_providers=(
                HeatTransferPhaseMetricProvider(
                    HeatTransferPhaseConfig(
                        solidus=1605.0,
                        liquidus=1700.0,
                        threshold_band=10.0,
                    )
                ),
            ),
        )
        self.assertEqual(report.status, ResultStatus.INVALID)
        self.assertFalse(
            report.alignment_checks[
                "provider:heat-transfer.phase-change.v1:temperature_channel"
            ]
        )

    def test_nonthermal_poisson_field_uses_only_residual_provider(self) -> None:
        reference = np.ones((1, 4, 1, 1))
        prediction = np.array([[[[1.0]], [[1.1]], [[1.0]], [[0.9]]]])
        residual = np.array([[[[0.0]], [[0.2]], [[0.4]], [[0.6]]]])

        report = PredictionAnalyzer().analyze(
            report_id="poisson-residual",
            prediction=field(
                "poisson-prediction",
                prediction,
                channel="u",
                unit="1",
                context={"pde_residual": residual},
            ),
            reference=field(
                "poisson-reference",
                reference,
                channel="u",
                unit="1",
            ),
            domain_metric_providers=(ResidualMetricProvider(channel_name="u"),),
        )

        self.assertEqual(report.status, ResultStatus.VALID)
        self.assertAlmostEqual(
            report.domain_metrics["pde_residual_mean_abs"],
            0.3,
        )
        self.assertNotIn("phase_accuracy", report.domain_metrics)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.domain_metrics.base import DomainMetricContext  # noqa: E402
from pinn_strategy_system.domain_metrics.navier_stokes import (  # noqa: E402
    LidDrivenCavityMetricProvider,
)


class LidDrivenCavityDomainMetricTests(unittest.TestCase):
    def test_provider_reports_coupled_velocity_and_residual_metrics(self) -> None:
        x = np.linspace(0.0, 1.0, 9)
        y = np.linspace(0.0, 1.0, 9)
        yy, xx = np.meshgrid(y, x, indexing="ij")
        u = np.sin(np.pi * xx) * np.sin(np.pi * yy)
        v = -0.5 * np.sin(2.0 * np.pi * xx) * np.sin(np.pi * yy)
        reference = np.stack((u, v), axis=2)
        error = np.stack(
            (
                0.01 * xx * (1.0 - xx) * yy * (1.0 - yy),
                -0.02 * xx * (1.0 - xx) * yy * (1.0 - yy),
            ),
            axis=2,
        )
        pressure_gradient = np.stack((xx, yy), axis=2)
        continuity = np.full_like(reference, 0.01)
        momentum = np.full_like(reference, 0.02)
        continuity[[0, -1], :, :] = 100.0
        continuity[:, [0, -1], :] = 100.0
        momentum[[0, -1], :, :] = 100.0
        momentum[:, [0, -1], :] = 100.0
        result = LidDrivenCavityMetricProvider().evaluate(
            DomainMetricContext(
                prediction=reference + error,
                reference=reference,
                error=error,
                axes=("y", "x", "channel"),
                coordinates={"y": y, "x": x, "channel": np.asarray(("u", "v"))},
                context_fields={
                    "continuity_residual": continuity,
                    "momentum_residual": momentum,
                    "pressure_field": np.zeros_like(reference),
                    "pressure_gradient": pressure_gradient + 0.01,
                    "reference_pressure_gradient": pressure_gradient,
                },
            )
        )

        self.assertTrue(all(result.checks.values()), result.findings)
        self.assertGreater(result.metrics["ns_velocity_relative_l2"], 0.0)
        self.assertGreater(result.metrics["ns_velocity_vector_max_abs"], 0.0)
        self.assertEqual(result.metrics["ns_wall_velocity_max_abs"], 0.0)
        self.assertAlmostEqual(result.metrics["ns_continuity_rms"], 0.01)
        self.assertAlmostEqual(
            result.metrics["ns_momentum_rms"], np.sqrt(2.0) * 0.02
        )
        self.assertEqual(result.metrics["ns_pressure_mean_abs"], 0.0)

    def test_provider_requires_gauge_invariant_pressure_evidence(self) -> None:
        values = np.ones((3, 3, 2))
        result = LidDrivenCavityMetricProvider().evaluate(
            DomainMetricContext(
                prediction=values,
                reference=values,
                error=np.zeros_like(values),
                axes=("y", "x", "channel"),
                coordinates={
                    "y": np.arange(3.0),
                    "x": np.arange(3.0),
                    "channel": np.asarray(("u", "v")),
                },
            )
        )
        self.assertFalse(result.checks["pressure_gradient_present"])


if __name__ == "__main__":
    unittest.main()

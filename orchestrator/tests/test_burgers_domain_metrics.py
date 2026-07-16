from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.domain_metrics.base import DomainMetricContext  # noqa: E402
from pinn_strategy_system.domain_metrics.burgers import (  # noqa: E402
    BurgersMetricProvider,
)


class BurgersDomainMetricTests(unittest.TestCase):
    def test_provider_reports_time_space_constraints_and_gradient_region(self) -> None:
        time = np.linspace(0.0, 1.0, 5)
        space = np.linspace(-1.0, 1.0, 9)
        tt, xx = np.meshgrid(time, space, indexing="ij")
        reference = -np.exp(-tt) * np.tanh(5.0 * xx) * (1.0 - np.square(xx))
        error = 0.01 * tt * (1.0 - np.square(xx))
        prediction = reference + error
        residual = np.full_like(reference, 0.2)

        result = BurgersMetricProvider().evaluate(
            DomainMetricContext(
                prediction=prediction,
                reference=reference,
                error=error,
                axes=("t", "x"),
                coordinates={"t": time, "x": space},
                context_fields={"pde_residual": residual},
            )
        )

        self.assertTrue(all(result.checks.values()), result.findings)
        self.assertAlmostEqual(result.metrics["burgers_pde_residual_rms"], 0.2)
        self.assertEqual(result.metrics["burgers_initial_max_abs"], 0.0)
        self.assertEqual(result.metrics["burgers_boundary_max_abs"], 0.0)
        self.assertGreater(result.metrics["burgers_high_gradient_rmse"], 0.0)

    def test_provider_requires_residual_evidence(self) -> None:
        values = np.ones((2, 3))
        result = BurgersMetricProvider().evaluate(
            DomainMetricContext(
                prediction=values,
                reference=values,
                error=np.zeros_like(values),
                axes=("t", "x"),
                coordinates={"t": np.arange(2.0), "x": np.arange(3.0)},
            )
        )
        self.assertFalse(result.checks["pde_residual_present"])


if __name__ == "__main__":
    unittest.main()

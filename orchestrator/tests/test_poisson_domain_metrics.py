from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.domain_metrics.base import DomainMetricContext  # noqa: E402
from pinn_strategy_system.domain_metrics.poisson import (  # noqa: E402
    PoissonMetricProvider,
)


class PoissonDomainMetricTests(unittest.TestCase):
    def test_provider_reports_nonthermal_elliptic_metrics(self) -> None:
        x = np.linspace(0.0, 1.0, 9)
        y = np.linspace(0.0, 1.0, 9)
        xx, yy = np.meshgrid(x, y, indexing="ij")
        reference = np.sin(math.pi * xx) * np.sin(math.pi * yy)
        prediction = 0.9 * reference
        error = prediction - reference
        residual = 0.2 * np.ones_like(error)
        boundary_error = prediction.copy()

        result = PoissonMetricProvider().evaluate(
            DomainMetricContext(
                prediction=prediction,
                reference=reference,
                error=error,
                axes=("x", "y"),
                coordinates={"x": x, "y": y},
                context_fields={
                    "pde_residual": residual,
                    "boundary_error": boundary_error,
                },
            )
        )

        self.assertTrue(all(result.checks.values()), result.findings)
        self.assertAlmostEqual(result.metrics["poisson_relative_h1"], 0.1)
        self.assertAlmostEqual(result.metrics["poisson_pde_residual_rms"], 0.2)
        self.assertLess(result.metrics["poisson_boundary_max_abs"], 1.0e-12)

    def test_provider_rejects_missing_residual_evidence(self) -> None:
        values = np.ones((3, 3))
        result = PoissonMetricProvider().evaluate(
            DomainMetricContext(
                prediction=values,
                reference=values,
                error=np.zeros_like(values),
                axes=("x", "y"),
                coordinates={"x": np.arange(3.0), "y": np.arange(3.0)},
                context_fields={"boundary_error": np.zeros_like(values)},
            )
        )
        self.assertFalse(result.checks["pde_residual_present"])


if __name__ == "__main__":
    unittest.main()

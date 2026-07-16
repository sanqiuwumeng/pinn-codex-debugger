from __future__ import annotations

import sys
import unittest
from pathlib import Path

import torch

CASE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_ROOT))

from cavity_pinn_worker import CavityNet, pde_residual, sample_points  # noqa: E402


class LidCavityWorkerTests(unittest.TestCase):
    def test_hard_velocity_transform_enforces_approved_walls(self) -> None:
        torch.manual_seed(7)
        model = CavityNet()
        wall_points = torch.tensor(
            [
                [0.0, 0.0],
                [0.25, 0.0],
                [1.0, 0.0],
                [0.0, 0.25],
                [1.0, 0.75],
                [0.0, 1.0],
                [0.25, 1.0],
                [0.50, 1.0],
                [0.75, 1.0],
                [1.0, 1.0],
            ],
            dtype=torch.float32,
        )
        velocity = model(wall_points)[:, :2].detach()
        expected_u = torch.tensor(
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0]
        )
        torch.testing.assert_close(velocity[:, 0], expected_u, atol=1.0e-7, rtol=0.0)
        torch.testing.assert_close(
            velocity[:, 1], torch.zeros(10), atol=1.0e-7, rtol=0.0
        )

    def test_residuals_cover_continuity_and_both_momentum_equations(self) -> None:
        torch.manual_seed(42)
        model = CavityNet()
        points = torch.rand((16, 2)) * 0.8 + 0.1
        continuity, momentum_x, momentum_y, fields = pde_residual(
            model, points, create_graph=True
        )
        for tensor in (continuity, momentum_x, momentum_y):
            self.assertEqual(tensor.shape, (16, 1))
            self.assertTrue(bool(torch.isfinite(tensor).all()))
        self.assertEqual(fields.shape, (16, 3))

    def test_focused_sampler_keeps_total_count_and_domain_confinement(self) -> None:
        torch.manual_seed(2026)
        points = sample_points(
            count=512,
            sampler="focused",
            focus_x=0.9,
            focus_y=0.8,
            focus_fraction=0.125,
            sigma=0.1,
            device=torch.device("cpu"),
        )
        self.assertEqual(points.shape, (512, 2))
        self.assertTrue(bool(torch.all(points > 0.0)))
        self.assertTrue(bool(torch.all(points < 1.0)))


if __name__ == "__main__":
    unittest.main()

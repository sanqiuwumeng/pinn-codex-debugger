"""Explicit metrics for two-dimensional incompressible Navier-Stokes fields."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import DomainMetricContext, DomainMetricResult


@dataclass(frozen=True)
class LidDrivenCavityMetricProvider:
    x_axis: str = "x"
    y_axis: str = "y"
    velocity_channels: tuple[str, str] = ("u", "v")
    high_shear_percentile: float = 90.0

    def __post_init__(self) -> None:
        if not 0.0 < self.high_shear_percentile < 100.0:
            raise ValueError("high_shear_percentile must be in (0, 100)")

    @property
    def provider_id(self) -> str:
        return "incompressible.navier-stokes.lid-cavity-2d.v1"

    def evaluate(self, context: DomainMetricContext) -> DomainMetricResult:
        values = np.asarray(context.prediction, dtype=float)
        reference = np.asarray(context.reference, dtype=float)
        error = np.asarray(context.error, dtype=float)
        channels = np.asarray(context.coordinates.get("channel", ())).astype(str)
        checks = {
            "velocity_axes": context.axes == (
                self.y_axis,
                self.x_axis,
                "channel",
            ),
            "two_velocity_channels": tuple(channels) == self.velocity_channels,
            "matching_finite_fields": bool(
                values.shape == reference.shape == error.shape
                and values.ndim == 3
                and values.shape[-1] == 2
                and np.isfinite(values).all()
                and np.isfinite(reference).all()
                and np.isfinite(error).all()
            ),
        }
        findings: list[str] = []
        if not all(checks.values()):
            findings.append("lid-cavity metrics require finite y,x,(u,v) fields")
            return DomainMetricResult(checks=checks, findings=tuple(findings))

        x = np.asarray(context.coordinates[self.x_axis], dtype=float)
        y = np.asarray(context.coordinates[self.y_axis], dtype=float)
        checks.update(
            {
                "coordinate_sizes": len(x) >= 3 and len(y) >= 3,
                "strictly_increasing_coordinates": bool(
                    np.all(np.diff(x) > 0) and np.all(np.diff(y) > 0)
                ),
            }
        )
        required_context = (
            "continuity_residual",
            "momentum_residual",
            "pressure_field",
            "pressure_gradient",
            "reference_pressure_gradient",
        )
        for name in required_context:
            field = context.context_fields.get(name)
            checks[f"{name}_present"] = field is not None
            checks[f"{name}_aligned_finite"] = bool(
                field is not None
                and np.asarray(field).shape == values.shape
                and np.isfinite(field).all()
            )
        if not all(checks.values()):
            findings.append("NS residual or pressure-gradient evidence is incomplete")
            return DomainMetricResult(checks=checks, findings=tuple(findings))

        vector_error = np.sqrt(np.sum(np.square(error), axis=2))
        reference_energy = float(np.sum(np.square(reference)))
        checks["velocity_relative_l2_defined"] = reference_energy > 0.0
        if not checks["velocity_relative_l2_defined"]:
            findings.append("reference velocity norm is zero")
            return DomainMetricResult(checks=checks, findings=tuple(findings))

        center_x = int(np.argmin(np.abs(x - 0.5)))
        center_y = int(np.argmin(np.abs(y - 0.5)))
        centerline_error = np.concatenate(
            (error[:, center_x, 0], error[center_y, :, 1])
        )
        wall_error = np.concatenate(
            (
                vector_error[0, 1:-1],
                vector_error[-1, 1:-1],
                vector_error[1:-1, 0],
                vector_error[1:-1, -1],
            )
        )
        du_dy, du_dx = np.gradient(reference[:, :, 0], y, x, edge_order=2)
        dv_dy, dv_dx = np.gradient(reference[:, :, 1], y, x, edge_order=2)
        shear_magnitude = np.sqrt(
            np.square(du_dx)
            + np.square(du_dy)
            + np.square(dv_dx)
            + np.square(dv_dy)
        )
        shear_threshold = float(
            np.percentile(shear_magnitude, self.high_shear_percentile)
        )
        shear_mask = shear_magnitude >= shear_threshold
        checks["high_shear_region_nonempty"] = bool(np.any(shear_mask))

        continuity = np.asarray(
            context.context_fields["continuity_residual"], dtype=float
        )[1:-1, 1:-1, 0]
        momentum = np.asarray(
            context.context_fields["momentum_residual"], dtype=float
        )[1:-1, 1:-1, :]
        pressure_gradient = np.asarray(
            context.context_fields["pressure_gradient"], dtype=float
        )
        pressure_field = np.asarray(
            context.context_fields["pressure_field"], dtype=float
        )[:, :, 0]
        reference_pressure_gradient = np.asarray(
            context.context_fields["reference_pressure_gradient"], dtype=float
        )
        pressure_denominator = float(np.linalg.norm(reference_pressure_gradient))
        checks["pressure_gradient_relative_l2_defined"] = pressure_denominator > 0.0
        if not all(checks.values()):
            findings.append("high-shear or pressure-gradient metric is undefined")
            return DomainMetricResult(checks=checks, findings=tuple(findings))

        metrics = {
            "ns_velocity_relative_l2": float(
                np.sqrt(np.sum(np.square(error)) / reference_energy)
            ),
            "ns_velocity_vector_max_abs": float(np.max(vector_error)),
            "ns_centerline_velocity_rmse": float(
                np.sqrt(np.mean(np.square(centerline_error)))
            ),
            "ns_wall_velocity_max_abs": float(np.max(wall_error)),
            "ns_continuity_rms": float(
                np.sqrt(np.mean(np.square(continuity)))
            ),
            "ns_momentum_rms": float(
                np.sqrt(np.mean(np.sum(np.square(momentum), axis=2)))
            ),
            "ns_pressure_mean_abs": float(np.abs(np.mean(pressure_field))),
            "ns_pressure_gradient_relative_l2": float(
                np.linalg.norm(pressure_gradient - reference_pressure_gradient)
                / pressure_denominator
            ),
            "ns_high_shear_velocity_rmse": float(
                np.sqrt(np.mean(np.square(vector_error[shear_mask])))
            ),
            "ns_reference_shear_threshold": shear_threshold,
        }
        return DomainMetricResult(
            metrics=metrics,
            checks=checks,
            findings=tuple(findings),
        )

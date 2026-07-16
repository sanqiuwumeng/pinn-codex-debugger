"""Explicit metrics for scalar time-dependent viscous Burgers fields."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import DomainMetricContext, DomainMetricResult, select_channel


@dataclass(frozen=True)
class BurgersMetricProvider:
    solution_channel: str | None = "u"
    time_axis: str = "t"
    space_axis: str = "x"
    high_gradient_percentile: float = 90.0

    def __post_init__(self) -> None:
        if not 0.0 < self.high_gradient_percentile < 100.0:
            raise ValueError("high_gradient_percentile must be in (0, 100)")

    @property
    def provider_id(self) -> str:
        return "nonlinear.burgers-1d.v1"

    def evaluate(self, context: DomainMetricContext) -> DomainMetricResult:
        error, axes = select_channel(
            np.asarray(context.error),
            axes=context.axes,
            coordinates=context.coordinates,
            channel_name=self.solution_channel,
        )
        reference, reference_axes = select_channel(
            np.asarray(context.reference),
            axes=context.axes,
            coordinates=context.coordinates,
            channel_name=self.solution_channel,
        )
        checks = {
            "solution_channel": error is not None and reference is not None,
            "time_space_axes": axes == (self.time_axis, self.space_axis),
            "reference_axes": reference_axes == axes,
        }
        findings: list[str] = []
        if not checks["solution_channel"]:
            findings.append("configured scalar solution channel is absent or ambiguous")
        if not checks["time_space_axes"]:
            findings.append("Burgers metrics require explicit t and x field axes")
        if not all(checks.values()) or error is None or reference is None:
            return DomainMetricResult(checks=checks, findings=tuple(findings))

        time = np.asarray(context.coordinates[self.time_axis], dtype=float)
        space = np.asarray(context.coordinates[self.space_axis], dtype=float)
        checks.update(
            {
                "coordinate_sizes": len(time) >= 2 and len(space) >= 3,
                "strictly_increasing_coordinates": bool(
                    np.all(np.diff(time) > 0) and np.all(np.diff(space) > 0)
                ),
                "finite_fields": bool(
                    np.isfinite(error).all() and np.isfinite(reference).all()
                ),
            }
        )
        residual = context.context_fields.get("pde_residual")
        checks["pde_residual_present"] = residual is not None
        if not all(checks.values()):
            findings.append("Burgers metric inputs are incomplete or invalid")
            return DomainMetricResult(checks=checks, findings=tuple(findings))

        residual_view, residual_axes = select_channel(
            np.asarray(residual),
            axes=context.axes,
            coordinates=context.coordinates,
            channel_name=self.solution_channel,
        )
        checks["pde_residual_aligned"] = (
            residual_view is not None and residual_axes == axes
        )
        checks["pde_residual_finite"] = bool(
            residual_view is not None and np.isfinite(residual_view).all()
        )
        if not all(checks.values()) or residual_view is None:
            findings.append("Burgers PDE residual is absent, misaligned or non-finite")
            return DomainMetricResult(checks=checks, findings=tuple(findings))

        reference_gradient = np.gradient(reference, space, axis=1, edge_order=2)
        gradient_magnitude = np.abs(reference_gradient)
        gradient_threshold = float(
            np.percentile(gradient_magnitude, self.high_gradient_percentile)
        )
        high_gradient_mask = gradient_magnitude >= gradient_threshold
        checks["high_gradient_region_nonempty"] = bool(np.any(high_gradient_mask))
        if not checks["high_gradient_region_nonempty"]:
            findings.append("reference high-gradient region is empty")
            return DomainMetricResult(checks=checks, findings=tuple(findings))

        high_gradient_error = error[high_gradient_mask]
        boundary_error = np.concatenate((error[:, 0], error[:, -1]))
        metrics = {
            "burgers_pde_residual_rms": float(
                np.sqrt(np.mean(np.square(residual_view)))
            ),
            "burgers_initial_max_abs": float(np.max(np.abs(error[0]))),
            "burgers_boundary_max_abs": float(np.max(np.abs(boundary_error))),
            "burgers_high_gradient_rmse": float(
                np.sqrt(np.mean(np.square(high_gradient_error)))
            ),
            "burgers_high_gradient_max_abs": float(
                np.max(np.abs(high_gradient_error))
            ),
            "burgers_reference_gradient_threshold": gradient_threshold,
        }
        return DomainMetricResult(
            metrics=metrics,
            checks=checks,
            findings=tuple(findings),
        )

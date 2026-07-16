"""Explicit metrics for scalar two-dimensional Poisson fields."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import DomainMetricContext, DomainMetricResult, select_channel


@dataclass(frozen=True)
class PoissonMetricProvider:
    solution_channel: str | None = "u"
    x_axis: str = "x"
    y_axis: str = "y"

    @property
    def provider_id(self) -> str:
        return "elliptic.poisson-2d.v1"

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
            "two_dimensional_axes": axes == (self.x_axis, self.y_axis),
            "reference_axes": reference_axes == axes,
        }
        findings: list[str] = []
        if not checks["solution_channel"]:
            findings.append("configured scalar solution channel is absent or ambiguous")
        if not checks["two_dimensional_axes"]:
            findings.append("Poisson metrics require explicit x and y field axes")
        if not all(checks.values()) or error is None or reference is None:
            return DomainMetricResult(checks=checks, findings=tuple(findings))

        x = np.asarray(context.coordinates[self.x_axis], dtype=float)
        y = np.asarray(context.coordinates[self.y_axis], dtype=float)
        checks["coordinate_sizes"] = len(x) >= 3 and len(y) >= 3
        checks["strictly_increasing_coordinates"] = bool(
            np.all(np.diff(x) > 0) and np.all(np.diff(y) > 0)
        )
        checks["finite_fields"] = bool(
            np.isfinite(error).all() and np.isfinite(reference).all()
        )
        if not all(checks.values()):
            findings.append("Poisson gradient metrics require finite fields on a regular ordering")
            return DomainMetricResult(checks=checks, findings=tuple(findings))

        error_gradients = np.gradient(error, x, y, edge_order=2)
        reference_gradients = np.gradient(reference, x, y, edge_order=2)
        gradient_error_energy = sum(
            float(np.mean(np.square(component))) for component in error_gradients
        )
        reference_gradient_energy = sum(
            float(np.mean(np.square(component))) for component in reference_gradients
        )
        checks["relative_h1_defined"] = reference_gradient_energy > 0.0
        metrics = {
            "poisson_h1_seminorm_error": float(np.sqrt(gradient_error_energy)),
        }
        if checks["relative_h1_defined"]:
            metrics["poisson_relative_h1"] = float(
                np.sqrt(gradient_error_energy / reference_gradient_energy)
            )

        residual = context.context_fields.get("pde_residual")
        checks["pde_residual_present"] = residual is not None
        if residual is not None:
            residual_view, residual_axes = select_channel(
                np.asarray(residual),
                axes=context.axes,
                coordinates=context.coordinates,
                channel_name=self.solution_channel,
            )
            checks["pde_residual_aligned"] = (
                residual_view is not None and residual_axes == axes
            )
            if residual_view is not None and residual_axes == axes:
                checks["pde_residual_finite"] = bool(np.isfinite(residual_view).all())
                if checks["pde_residual_finite"]:
                    metrics["poisson_pde_residual_rms"] = float(
                        np.sqrt(np.mean(np.square(residual_view)))
                    )

        boundary_error = context.context_fields.get("boundary_error")
        checks["boundary_error_present"] = boundary_error is not None
        if boundary_error is not None:
            boundary_view, boundary_axes = select_channel(
                np.asarray(boundary_error),
                axes=context.axes,
                coordinates=context.coordinates,
                channel_name=self.solution_channel,
            )
            checks["boundary_error_aligned"] = (
                boundary_view is not None and boundary_axes == axes
            )
            if boundary_view is not None and boundary_axes == axes:
                boundary_values = np.concatenate(
                    (
                        boundary_view[0, :],
                        boundary_view[-1, :],
                        boundary_view[1:-1, 0],
                        boundary_view[1:-1, -1],
                    )
                )
                checks["boundary_error_finite"] = bool(
                    np.isfinite(boundary_values).all()
                )
                if checks["boundary_error_finite"]:
                    metrics["poisson_boundary_max_abs"] = float(
                        np.max(np.abs(boundary_values))
                    )

        missing = tuple(name for name, passed in checks.items() if not passed)
        if missing:
            findings.append(f"Poisson metric checks failed: {', '.join(missing)}")
        return DomainMetricResult(
            metrics=metrics,
            checks=checks,
            findings=tuple(findings),
        )

"""Domain-neutral PINN residual and constraint metrics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import DomainMetricContext, DomainMetricResult, select_channel


@dataclass(frozen=True)
class ResidualMetricProvider:
    channel_name: str | None = None

    @property
    def provider_id(self) -> str:
        return "pinn.residual.v1"

    def evaluate(self, context: DomainMetricContext) -> DomainMetricResult:
        metrics: dict[str, float] = {}
        checks: dict[str, bool] = {}
        findings: list[str] = []

        residual = context.context_fields.get("pde_residual")
        if residual is not None:
            residual_view, _ = select_channel(
                np.asarray(residual),
                axes=context.axes,
                coordinates=context.coordinates,
                channel_name=self.channel_name,
            )
            checks["residual_channel"] = residual_view is not None
            if residual_view is None:
                findings.append("configured residual channel is absent or ambiguous")
            elif not np.issubdtype(residual_view.dtype, np.number):
                checks["residual_numeric"] = False
                findings.append("PDE residual must be numeric")
            else:
                residual_float = residual_view.astype(float, copy=False)
                checks["residual_numeric"] = True
                checks["residual_finite"] = bool(np.isfinite(residual_float).all())
                if checks["residual_finite"]:
                    metrics.update(
                        {
                            "pde_residual_mean_abs": float(
                                np.mean(np.abs(residual_float))
                            ),
                            "pde_residual_rms": float(
                                np.sqrt(np.mean(np.square(residual_float)))
                            ),
                            "pde_residual_max_abs": float(
                                np.max(np.abs(residual_float))
                            ),
                        }
                    )
                else:
                    findings.append("PDE residual contains NaN or infinity")

        violation = context.context_fields.get("bc_ic_violation")
        if violation is not None:
            violation_view, _ = select_channel(
                np.asarray(violation, dtype=bool),
                axes=context.axes,
                coordinates=context.coordinates,
                channel_name=self.channel_name,
            )
            checks["bc_ic_channel"] = violation_view is not None
            if violation_view is None:
                findings.append("configured BC/IC channel is absent or ambiguous")
            else:
                metrics["bc_ic_violation_fraction"] = float(
                    np.mean(violation_view)
                )

        return DomainMetricResult(
            metrics=metrics,
            checks=checks,
            findings=tuple(findings),
        )

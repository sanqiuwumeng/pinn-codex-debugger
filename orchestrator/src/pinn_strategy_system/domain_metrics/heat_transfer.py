"""Optional heat-transfer phase metrics; never imported by the generic analyzer."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

import numpy as np

from .base import DomainMetricContext, DomainMetricResult, select_channel


@dataclass(frozen=True)
class HeatTransferPhaseConfig:
    solidus: float
    liquidus: float
    threshold_band: float
    temperature_channel: str = "temperature"

    def __post_init__(self) -> None:
        if not math.isfinite(self.solidus) or not math.isfinite(self.liquidus):
            raise ValueError("solidus and liquidus must be finite")
        if self.liquidus <= self.solidus:
            raise ValueError("liquidus must be greater than solidus")
        if not math.isfinite(self.threshold_band) or self.threshold_band < 0:
            raise ValueError("threshold_band must be finite and nonnegative")


@dataclass(frozen=True)
class HeatTransferPhaseMetricProvider:
    config: HeatTransferPhaseConfig

    @property
    def provider_id(self) -> str:
        return "heat-transfer.phase-change.v1"

    def evaluate(self, context: DomainMetricContext) -> DomainMetricResult:
        predicted, view_axes = select_channel(
            context.prediction,
            axes=context.axes,
            coordinates=context.coordinates,
            channel_name=self.config.temperature_channel,
        )
        reference, _ = select_channel(
            context.reference,
            axes=context.axes,
            coordinates=context.coordinates,
            channel_name=self.config.temperature_channel,
        )
        error, _ = select_channel(
            context.error,
            axes=context.axes,
            coordinates=context.coordinates,
            channel_name=self.config.temperature_channel,
        )
        if predicted is None or reference is None or error is None:
            return DomainMetricResult(
                checks={"temperature_channel": False},
                findings=(
                    "configured heat-transfer channel is absent or ambiguous",
                ),
            )

        predicted_phase = _phase_labels(predicted, self.config)
        reference_phase = _phase_labels(reference, self.config)
        metrics = {
            "phase_accuracy": float(np.mean(predicted_phase == reference_phase)),
            "solid_mask_iou": _mask_iou(
                predicted_phase == 0,
                reference_phase == 0,
            ),
            "mushy_mask_iou": _mask_iou(
                predicted_phase == 1,
                reference_phase == 1,
            ),
            "liquid_mask_iou": _mask_iou(
                predicted_phase == 2,
                reference_phase == 2,
            ),
            "predicted_liquid_fraction": float(np.mean(predicted_phase == 2)),
            "reference_liquid_fraction": float(np.mean(reference_phase == 2)),
        }
        metrics["liquid_fraction_abs_error"] = abs(
            metrics["predicted_liquid_fraction"]
            - metrics["reference_liquid_fraction"]
        )

        threshold_mask = (
            np.abs(reference - self.config.solidus) <= self.config.threshold_band
        ) | (
            np.abs(reference - self.config.liquidus) <= self.config.threshold_band
        )
        if np.any(threshold_mask):
            metrics["phase_threshold_band_mae"] = float(
                np.mean(np.abs(error[threshold_mask]))
            )
        metrics.update(
            _liquid_geometry_metrics(
                predicted_phase == 2,
                reference_phase == 2,
                view_axes,
                context.coordinates,
            )
        )

        sampling = context.context_fields.get("sampling_density")
        if sampling is not None:
            sampling_view, _ = select_channel(
                np.asarray(sampling, dtype=float),
                axes=context.axes,
                coordinates=context.coordinates,
                channel_name=self.config.temperature_channel,
            )
            if sampling_view is not None and np.any(threshold_mask):
                metrics["sampling_density_phase_band_mean"] = float(
                    np.mean(sampling_view[threshold_mask])
                )

        return DomainMetricResult(
            metrics=metrics,
            checks={"temperature_channel": True},
        )


def _phase_labels(
    temperature: np.ndarray,
    config: HeatTransferPhaseConfig,
) -> np.ndarray:
    labels = np.ones(temperature.shape, dtype=np.int8)
    labels[temperature < config.solidus] = 0
    labels[temperature >= config.liquidus] = 2
    return labels


def _mask_iou(predicted: np.ndarray, reference: np.ndarray) -> float:
    union = np.logical_or(predicted, reference)
    if not np.any(union):
        return 1.0
    return float(np.logical_and(predicted, reference).sum() / union.sum())


def _liquid_geometry_metrics(
    predicted_liquid: np.ndarray,
    reference_liquid: np.ndarray,
    axes: tuple[str, ...],
    coordinates: Mapping[str, np.ndarray],
) -> dict[str, float]:
    time_axis = axes.index("t") if "t" in axes else None
    time_indices = (
        range(predicted_liquid.shape[time_axis])
        if time_axis is not None
        else (None,)
    )
    spatial_axes = [axis for axis in axes if axis != "t"]
    errors: dict[str, list[float]] = {axis: [] for axis in spatial_axes}

    for time_index in time_indices:
        if time_index is None:
            predicted_slice = predicted_liquid
            reference_slice = reference_liquid
            slice_axes = axes
        else:
            predicted_slice = np.take(predicted_liquid, time_index, axis=time_axis)
            reference_slice = np.take(reference_liquid, time_index, axis=time_axis)
            slice_axes = tuple(axis for axis in axes if axis != "t")
        for axis in spatial_axes:
            slice_axis = slice_axes.index(axis)
            predicted_extent = _mask_extent(
                predicted_slice,
                slice_axis,
                np.asarray(coordinates[axis], dtype=float),
            )
            reference_extent = _mask_extent(
                reference_slice,
                slice_axis,
                np.asarray(coordinates[axis], dtype=float),
            )
            errors[axis].append(abs(predicted_extent - reference_extent))

    return {
        f"liquid_extent_{axis}_mae": float(np.mean(values))
        for axis, values in errors.items()
        if values
    }


def _mask_extent(
    mask: np.ndarray,
    axis: int,
    coordinates: np.ndarray,
) -> float:
    reduced_axes = tuple(index for index in range(mask.ndim) if index != axis)
    occupied = np.flatnonzero(np.any(mask, axis=reduced_axes) if reduced_axes else mask)
    if occupied.size < 2:
        return 0.0
    values = coordinates[occupied]
    return float(np.max(values) - np.min(values))

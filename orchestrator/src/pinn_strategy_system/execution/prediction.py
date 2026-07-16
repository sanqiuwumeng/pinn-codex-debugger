"""Deterministic aligned-field metrics and localized error analysis."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np
from scipy.ndimage import generate_binary_structure, label

from pinn_strategy_system.contracts import (
    ArtifactRef,
    ConnectedRegionSummary,
    LocalizedError,
    PredictionAnalysisReport,
    PredictionComparisonReport,
    ResultStatus,
    TimeSliceMetric,
)
from pinn_strategy_system.domain_metrics.base import (
    DomainMetricContext,
    DomainMetricProvider,
)


@dataclass(frozen=True)
class FieldData:
    """In-process field view; arrays never enter WorkflowState."""

    values: np.ndarray
    artifact_ref: ArtifactRef
    axes: tuple[str, ...]
    coordinates: Mapping[str, np.ndarray]
    reference_identity: str
    unit: str
    coordinate_system: str
    normalization: str
    context_fields: Mapping[str, np.ndarray] = field(default_factory=dict)


class PredictionAnalyzer:
    def analyze(
        self,
        *,
        report_id: str,
        prediction: FieldData,
        reference: FieldData,
        top_k: int = 10,
        percentiles: tuple[float, ...] = (50.0, 90.0, 95.0, 99.0),
        connected_percentile: float = 95.0,
        roi_masks: Mapping[str, np.ndarray] | None = None,
        domain_metric_providers: tuple[DomainMetricProvider, ...] = (),
    ) -> PredictionAnalysisReport:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        if any(value < 0 or value > 100 for value in percentiles):
            raise ValueError("percentiles must be in [0, 100]")
        if not 0 <= connected_percentile <= 100:
            raise ValueError("connected_percentile must be in [0, 100]")

        checks, findings = _alignment(prediction, reference)
        masks = roi_masks or {}
        for name, mask in masks.items():
            checks[f"roi_shape:{name}"] = np.asarray(mask).shape == prediction.values.shape
            if not checks[f"roi_shape:{name}"]:
                findings.append(f"ROI mask {name} does not match the field shape")

        for name, context in prediction.context_fields.items():
            checks[f"context_shape:{name}"] = (
                np.asarray(context).shape == prediction.values.shape
            )
            if not checks[f"context_shape:{name}"]:
                findings.append(
                    f"context field {name} does not match the prediction shape"
                )

        if not checks or not all(checks.values()):
            return _invalid_report(
                report_id,
                prediction,
                reference,
                checks,
                findings,
            )

        predicted = np.asarray(prediction.values)
        truth = np.asarray(reference.values)
        checks["nonempty"] = predicted.size > 0
        checks["numeric_values"] = bool(
            np.issubdtype(predicted.dtype, np.number)
            and np.issubdtype(truth.dtype, np.number)
        )
        if not checks["nonempty"]:
            findings.append("aligned fields are empty")
        if not checks["numeric_values"]:
            findings.append("prediction and reference fields must be numeric arrays")
        checks["finite_values"] = bool(
            checks["numeric_values"]
            and np.isfinite(predicted).all()
            and np.isfinite(truth).all()
        )
        if checks["numeric_values"] and not checks["finite_values"]:
            findings.append("prediction or reference contains NaN or infinity")

        reference_norm = float(np.linalg.norm(truth.ravel()))
        checks["relative_l2_defined"] = reference_norm > 0
        if not checks["relative_l2_defined"]:
            findings.append("relative L2 is undefined because the reference norm is zero")

        if not all(checks.values()):
            return _invalid_report(
                report_id,
                prediction,
                reference,
                checks,
                findings,
            )

        error = predicted.astype(float, copy=False) - truth.astype(float, copy=False)
        absolute_error = np.abs(error)
        domain_metrics, provider_checks, provider_findings = _evaluate_providers(
            domain_metric_providers,
            DomainMetricContext(
                prediction=predicted,
                reference=truth,
                error=error,
                axes=prediction.axes,
                coordinates=prediction.coordinates,
                context_fields=prediction.context_fields,
            ),
        )
        checks.update(provider_checks)
        findings.extend(provider_findings)
        if not all(checks.values()):
            return _invalid_report(
                report_id,
                prediction,
                reference,
                checks,
                findings,
            )
        global_metrics = _metrics(error, truth)
        flat_order = np.argsort(-absolute_error.ravel(), kind="stable")
        points = tuple(
            _localized_error(
                int(flat_index),
                prediction,
                reference,
                error,
            )
            for flat_index in flat_order[: min(top_k, absolute_error.size)]
        )
        percentile_errors = {
            _percentile_name(value): float(np.percentile(absolute_error, value))
            for value in percentiles
        }
        threshold = float(np.percentile(absolute_error, connected_percentile))
        regions = _connected_regions(
            absolute_error,
            prediction,
            threshold=threshold,
        )
        time_slices = _time_slices(error, truth, prediction)
        roi_metrics = _roi_metrics(error, truth, masks)
        return PredictionAnalysisReport(
            report_id=report_id,
            status=ResultStatus.VALID,
            prediction_ref=prediction.artifact_ref,
            reference_ref=reference.artifact_ref,
            global_metrics=global_metrics,
            percentile_errors=percentile_errors,
            max_abs=points[0],
            top_k=points,
            connected_regions=regions,
            time_slices=time_slices,
            roi_metrics=roi_metrics,
            domain_metrics=domain_metrics,
            alignment_checks=checks,
            findings=tuple(findings),
        )

    def compare(
        self,
        *,
        report_id: str,
        baseline: FieldData,
        candidate: FieldData,
        reference: FieldData,
        migration_ratio: float = 0.8,
        **analysis_options: Any,
    ) -> PredictionComparisonReport:
        if not 0 <= migration_ratio <= 1:
            raise ValueError("migration_ratio must be in [0, 1]")
        baseline_report = self.analyze(
            report_id=f"{report_id}:baseline",
            prediction=baseline,
            reference=reference,
            **analysis_options,
        )
        candidate_report = self.analyze(
            report_id=f"{report_id}:candidate",
            prediction=candidate,
            reference=reference,
            **analysis_options,
        )
        status = (
            ResultStatus.VALID
            if baseline_report.status is ResultStatus.VALID
            and candidate_report.status is ResultStatus.VALID
            else ResultStatus.INVALID
        )
        common_metrics = (
            baseline_report.global_metrics.keys()
            & candidate_report.global_metrics.keys()
        )
        deltas = {
            name: candidate_report.global_metrics[name]
            - baseline_report.global_metrics[name]
            for name in sorted(common_metrics)
        }
        migrated = False
        findings: list[str] = []
        if status is ResultStatus.VALID:
            baseline_max = baseline_report.max_abs
            candidate_max = candidate_report.max_abs
            if baseline_max is None or candidate_max is None:
                status = ResultStatus.INVALID
                findings.append(
                    "a valid comparison report unexpectedly lacks max_abs localization"
                )
            else:
                changed_location = (
                    baseline_max.coordinates != candidate_max.coordinates
                )
                comparable_extreme = (
                    candidate_max.absolute_error
                    >= baseline_max.absolute_error * migration_ratio
                )
                migrated = changed_location and comparable_extreme
                if migrated:
                    findings.append(
                        "maximum error moved to a different coordinate while remaining "
                        "within the configured comparable-extreme ratio"
                    )
        else:
            findings.append(
                "baseline/candidate comparison is invalid until both fields align "
                "with the same reference"
            )
        return PredictionComparisonReport(
            report_id=report_id,
            status=status,
            baseline_report=baseline_report,
            candidate_report=candidate_report,
            metric_deltas=deltas,
            error_migrated=migrated,
            findings=tuple(findings),
        )


def _alignment(
    prediction: FieldData,
    reference: FieldData,
) -> tuple[dict[str, bool], list[str]]:
    checks = {
        "prediction_descriptor": _descriptor_is_valid(prediction),
        "reference_descriptor": _descriptor_is_valid(reference),
        "shape": prediction.values.shape == reference.values.shape,
        "axes": prediction.axes == reference.axes,
        "reference_identity": (
            prediction.reference_identity == reference.reference_identity
        ),
        "unit": prediction.unit == reference.unit,
        "coordinate_system": (
            prediction.coordinate_system == reference.coordinate_system
        ),
        "normalization": prediction.normalization == reference.normalization,
    }
    coordinates_match = (
        prediction.axes == reference.axes
        and all(
            axis in prediction.coordinates
            and axis in reference.coordinates
            and np.array_equal(
                np.asarray(prediction.coordinates[axis]),
                np.asarray(reference.coordinates[axis]),
            )
            for axis in prediction.axes
        )
    )
    checks["coordinates"] = coordinates_match
    findings = [
        f"alignment check failed: {name}"
        for name, passed in checks.items()
        if not passed
    ]
    return checks, findings


def _descriptor_is_valid(field_data: FieldData) -> bool:
    if len(field_data.axes) != field_data.values.ndim:
        return False
    if len(set(field_data.axes)) != len(field_data.axes):
        return False
    if set(field_data.coordinates) != set(field_data.axes):
        return False
    return all(
        np.asarray(field_data.coordinates[axis]).ndim == 1
        and len(field_data.coordinates[axis]) == field_data.values.shape[index]
        for index, axis in enumerate(field_data.axes)
    )


def _invalid_report(
    report_id: str,
    prediction: FieldData,
    reference: FieldData,
    checks: Mapping[str, bool],
    findings: list[str],
) -> PredictionAnalysisReport:
    return PredictionAnalysisReport(
        report_id=report_id,
        status=ResultStatus.INVALID,
        prediction_ref=prediction.artifact_ref,
        reference_ref=reference.artifact_ref,
        alignment_checks=dict(checks),
        findings=tuple(findings),
    )


def _metrics(error: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    flat_error = error.ravel()
    flat_reference = reference.ravel()
    mse = float(np.mean(np.square(flat_error)))
    denominator = float(np.linalg.norm(flat_reference))
    metrics = {
        "mse": mse,
        "rmse": math.sqrt(mse),
        "mae": float(np.mean(np.abs(flat_error))),
        "max_abs": float(np.max(np.abs(flat_error))),
    }
    if denominator > 0:
        metrics["relative_l2"] = float(np.linalg.norm(flat_error) / denominator)
    return metrics


def _localized_error(
    flat_index: int,
    prediction: FieldData,
    reference: FieldData,
    error: np.ndarray,
) -> LocalizedError:
    index = np.unravel_index(flat_index, error.shape)
    coordinates = {
        axis: _json_scalar(prediction.coordinates[axis][axis_index])
        for axis, axis_index in zip(prediction.axes, index, strict=True)
    }
    context = {
        name: _json_scalar(np.asarray(values)[index])
        for name, values in prediction.context_fields.items()
    }
    signed = float(error[index])
    return LocalizedError(
        flat_index=flat_index,
        coordinates=coordinates,
        prediction=float(np.asarray(prediction.values)[index]),
        reference=float(np.asarray(reference.values)[index]),
        signed_error=signed,
        absolute_error=abs(signed),
        context=context,
    )


def _connected_regions(
    absolute_error: np.ndarray,
    field_data: FieldData,
    *,
    threshold: float,
) -> tuple[ConnectedRegionSummary, ...]:
    spatial_axes = [
        axis for axis in field_data.axes if axis not in {"t", "channel"}
    ]
    if not spatial_axes:
        return ()

    time_indices = (
        range(field_data.values.shape[field_data.axes.index("t")])
        if "t" in field_data.axes
        else (None,)
    )
    channel_indices = (
        range(field_data.values.shape[field_data.axes.index("channel")])
        if "channel" in field_data.axes
        else (None,)
    )
    regions: list[ConnectedRegionSummary] = []

    for time_index, channel_index in itertools.product(
        time_indices,
        channel_indices,
    ):
        selector: list[int | slice] = [slice(None)] * absolute_error.ndim
        if time_index is not None:
            selector[field_data.axes.index("t")] = time_index
        if channel_index is not None:
            selector[field_data.axes.index("channel")] = channel_index
        spatial_error = absolute_error[tuple(selector)]
        hot = (spatial_error >= threshold) & (spatial_error > 0)
        if not np.any(hot):
            continue
        labels, count = label(
            hot,
            structure=generate_binary_structure(hot.ndim, 1),
        )
        for component_id in range(1, count + 1):
            positions = np.argwhere(labels == component_id)
            if positions.size == 0:
                continue
            centroid: dict[str, float] = {}
            bounds: dict[str, tuple[float, float]] = {}
            for column, axis in enumerate(spatial_axes):
                coordinate_values = np.asarray(field_data.coordinates[axis])[
                    positions[:, column]
                ].astype(float)
                centroid[axis] = float(np.mean(coordinate_values))
                bounds[axis] = (
                    float(np.min(coordinate_values)),
                    float(np.max(coordinate_values)),
                )
            component_error = spatial_error[labels == component_id]
            suffix = "-".join(
                (
                    f"t{time_index}" if time_index is not None else "tall",
                    (
                        f"c{channel_index}"
                        if channel_index is not None
                        else "call"
                    ),
                    f"r{component_id}",
                )
            )
            regions.append(
                ConnectedRegionSummary(
                    region_id=f"region-{suffix}",
                    time_value=(
                        _json_scalar(field_data.coordinates["t"][time_index])
                        if time_index is not None
                        else None
                    ),
                    channel_value=(
                        _json_scalar(
                            field_data.coordinates["channel"][channel_index]
                        )
                        if channel_index is not None
                        else None
                    ),
                    point_count=int(len(positions)),
                    peak_absolute_error=float(np.max(component_error)),
                    centroid=centroid,
                    bounds=bounds,
                )
            )
    return tuple(regions)


def _time_slices(
    error: np.ndarray,
    reference: np.ndarray,
    field_data: FieldData,
) -> tuple[TimeSliceMetric, ...]:
    if "t" not in field_data.axes:
        return ()
    time_axis = field_data.axes.index("t")
    slices: list[TimeSliceMetric] = []
    for time_index in range(error.shape[time_axis]):
        slice_error = np.take(error, time_index, axis=time_axis)
        slice_reference = np.take(reference, time_index, axis=time_axis)
        relative_index = np.unravel_index(
            int(np.argmax(np.abs(slice_error))),
            slice_error.shape,
        )
        full_indices: list[int] = []
        relative_cursor = 0
        for axis_index in range(error.ndim):
            if axis_index == time_axis:
                full_indices.append(time_index)
            else:
                full_indices.append(int(relative_index[relative_cursor]))
                relative_cursor += 1
        location = {
            axis: _json_scalar(field_data.coordinates[axis][index])
            for axis, index in zip(field_data.axes, full_indices, strict=True)
        }
        slices.append(
            TimeSliceMetric(
                time_value=_json_scalar(
                    field_data.coordinates["t"][time_index]
                ),
                metrics=_metrics(slice_error, slice_reference),
                max_location=location,
            )
        )
    return tuple(slices)


def _roi_metrics(
    error: np.ndarray,
    reference: np.ndarray,
    masks: Mapping[str, np.ndarray],
) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for name, raw_mask in masks.items():
        mask = np.asarray(raw_mask, dtype=bool)
        if mask.shape != error.shape or not np.any(mask):
            continue
        metrics[name] = _metrics(error[mask], reference[mask])
    return metrics


def _evaluate_providers(
    providers: tuple[DomainMetricProvider, ...],
    context: DomainMetricContext,
) -> tuple[dict[str, float], dict[str, bool], list[str]]:
    metrics: dict[str, float] = {}
    checks: dict[str, bool] = {}
    findings: list[str] = []
    provider_ids: set[str] = set()

    for provider in providers:
        provider_id = provider.provider_id.strip()
        if not provider_id or provider_id in provider_ids:
            checks[f"provider_identity:{provider_id or '<empty>'}"] = False
            findings.append("domain metric provider ids must be non-empty and unique")
            continue
        provider_ids.add(provider_id)
        result = provider.evaluate(context)
        checks.update(
            {
                f"provider:{provider_id}:{name}": passed
                for name, passed in result.checks.items()
            }
        )
        findings.extend(
            f"provider {provider_id}: {finding}"
            for finding in result.findings
        )
        for name, value in result.metrics.items():
            check_name = f"provider:{provider_id}:metric:{name}"
            if name in metrics or not math.isfinite(float(value)):
                checks[check_name] = False
                findings.append(
                    f"provider {provider_id} emitted a duplicate or non-finite "
                    f"metric: {name}"
                )
                continue
            checks[check_name] = True
            metrics[name] = float(value)
    return metrics, checks, findings


def _percentile_name(value: float) -> str:
    return f"p{value:g}"


def _json_scalar(value: Any) -> str | int | float | bool | None:
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)

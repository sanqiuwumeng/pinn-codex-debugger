"""Explicit domain-metric provider boundary for aligned PINN fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

import numpy as np


@dataclass(frozen=True)
class DomainMetricContext:
    prediction: np.ndarray
    reference: np.ndarray
    error: np.ndarray
    axes: tuple[str, ...]
    coordinates: Mapping[str, np.ndarray]
    context_fields: Mapping[str, np.ndarray] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainMetricResult:
    metrics: Mapping[str, float] = field(default_factory=dict)
    checks: Mapping[str, bool] = field(default_factory=dict)
    findings: tuple[str, ...] = ()


class DomainMetricProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    def evaluate(self, context: DomainMetricContext) -> DomainMetricResult: ...


def select_channel(
    values: np.ndarray,
    *,
    axes: tuple[str, ...],
    coordinates: Mapping[str, np.ndarray],
    channel_name: str | None,
) -> tuple[np.ndarray | None, tuple[str, ...]]:
    """Return an explicit channel view, or ``None`` when selection is invalid."""

    if "channel" not in axes:
        return values, axes
    if channel_name is None:
        return values, axes
    channel_values = np.asarray(coordinates.get("channel", ())).astype(str)
    matches = np.flatnonzero(channel_values == channel_name)
    if len(matches) != 1:
        return None, axes
    channel_axis = axes.index("channel")
    return (
        np.take(values, int(matches[0]), axis=channel_axis),
        tuple(axis for axis in axes if axis != "channel"),
    )

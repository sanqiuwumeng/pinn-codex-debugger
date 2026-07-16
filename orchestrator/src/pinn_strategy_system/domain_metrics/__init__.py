"""Provider interfaces only; concrete domains require explicit module imports."""

from .base import DomainMetricContext, DomainMetricProvider, DomainMetricResult
from .registry import DomainProviderRegistry

__all__ = [
    "DomainMetricContext",
    "DomainMetricProvider",
    "DomainMetricResult",
    "DomainProviderRegistry",
]

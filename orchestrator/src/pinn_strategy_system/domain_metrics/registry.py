"""Instance-local provider selection without implicit domain activation."""

from __future__ import annotations

from collections.abc import Iterable

from .base import DomainMetricProvider


class DomainProviderRegistry:
    def __init__(self, providers: Iterable[DomainMetricProvider]) -> None:
        entries = tuple(providers)
        ids = tuple(provider.provider_id for provider in entries)
        if any(not provider_id.strip() for provider_id in ids):
            raise ValueError("domain provider ids must be non-empty")
        if len(set(ids)) != len(ids):
            raise ValueError("domain provider ids must be unique")
        self._providers = entries

    @property
    def available_ids(self) -> tuple[str, ...]:
        return tuple(provider.provider_id for provider in self._providers)

    def select(
        self,
        provider_ids: tuple[str, ...],
    ) -> tuple[DomainMetricProvider, ...]:
        if len(set(provider_ids)) != len(provider_ids):
            raise ValueError("selected domain provider ids must be unique")
        providers = {
            provider.provider_id: provider
            for provider in self._providers
        }
        missing = tuple(
            provider_id
            for provider_id in provider_ids
            if provider_id not in providers
        )
        if missing:
            raise KeyError(f"unknown domain providers: {', '.join(missing)}")
        return tuple(providers[provider_id] for provider_id in provider_ids)

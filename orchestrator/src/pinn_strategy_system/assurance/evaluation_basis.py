"""Compatibility gate between user model authority and reference evidence."""

from __future__ import annotations

from dataclasses import dataclass

from pint import UnitRegistry
from pint.errors import DimensionalityError, PintError

from pinn_strategy_system.contracts import (
    PhysicalModelAuthority,
    ReferenceEvidence,
)

from .physical import normalize_unit_text


@dataclass(frozen=True)
class EvaluationBasisResult:
    ready: bool
    checks: dict[str, bool]
    reasons: tuple[str, ...]


class EvaluationBasisService:
    def __init__(self, registry: UnitRegistry | None = None) -> None:
        self._registry = registry or UnitRegistry(
            autoconvert_offset_to_baseunit=True
        )

    def validate(
        self,
        *,
        authority: PhysicalModelAuthority,
        references: tuple[ReferenceEvidence, ...] = (),
    ) -> EvaluationBasisResult:
        checks = {
            "authority_confirmed": authority.confirmed_by_user,
            "unit_system_confirmed": authority.unit_system.confirmed_by_user,
            "reference_ids_unique": len({item.reference_id for item in references})
            == len(references),
        }
        reasons: list[str] = []

        for name, passed in checks.items():
            if not passed:
                reasons.append(f"evaluation-basis check failed: {name}")

        for reference in references:
            prefix = f"reference:{reference.reference_id}"
            authority_match = reference.authority_id == authority.authority_id
            channels_match = set(reference.output_channels).issubset(
                authority.output_channels
            )
            checks[f"{prefix}:authority"] = authority_match
            checks[f"{prefix}:channels"] = channels_match
            if not authority_match:
                reasons.append(
                    f"{reference.reference_id} targets another physical authority"
                )
            if not channels_match:
                reasons.append(
                    f"{reference.reference_id} contains undeclared output channels"
                )

            for channel in reference.output_channels:
                model_unit = authority.unit_system.quantity_units.get(channel)
                reference_unit = reference.channel_units[channel]
                unit_check = f"{prefix}:unit:{channel}"
                checks[unit_check] = self._units_are_compatible(
                    reference_unit,
                    model_unit,
                )
                if not checks[unit_check]:
                    reasons.append(
                        f"{reference.reference_id} channel {channel} is incompatible "
                        "with the model unit system"
                    )

        return EvaluationBasisResult(
            ready=all(checks.values()),
            checks=checks,
            reasons=tuple(reasons),
        )

    def _units_are_compatible(
        self,
        reference_unit: str,
        model_unit: str | None,
    ) -> bool:
        if model_unit is None:
            return False
        try:
            self._registry.Quantity(
                1.0,
                normalize_unit_text(reference_unit),
            ).to(normalize_unit_text(model_unit))
        except (DimensionalityError, PintError):
            return False
        return True

"""Traceable physical-parameter, dimensional and scaling audits."""

from __future__ import annotations

import math
from collections.abc import Iterable

from pint import UnitRegistry
from pint.errors import DimensionalityError, PintError

from pinn_strategy_system.contracts import (
    AuditFinding,
    AuditStatus,
    DerivativeScalingSpec,
    EquationAuditSpec,
    ParameterConsumption,
    PhysicalAuditReport,
    PhysicalParameterInput,
    PhysicalParameterRecord,
    UnitSystemContract,
)


class PhysicalAuditService:
    """Audit physical inputs using an instance-local Pint registry."""

    def __init__(
        self,
        registry: UnitRegistry | None = None,
        *,
        relative_tolerance: float = 1e-9,
    ) -> None:
        self._registry = registry or UnitRegistry(
            autoconvert_offset_to_baseunit=True
        )
        self._relative_tolerance = relative_tolerance

    def audit(
        self,
        *,
        report_id: str,
        unit_system: UnitSystemContract,
        parameters: Iterable[PhysicalParameterInput],
        equations: Iterable[EquationAuditSpec] = (),
        derivative_scaling: Iterable[DerivativeScalingSpec] = (),
    ) -> PhysicalAuditReport:
        records: list[PhysicalParameterRecord] = []
        findings: list[AuditFinding] = []

        if not unit_system.confirmed_by_user:
            findings.append(
                AuditFinding(
                    code="UNIT_SYSTEM_UNCONFIRMED",
                    status=AuditStatus.NEEDS_UNIT_CONFIRMATION,
                    message="The model-internal unit system requires user confirmation.",
                    source_refs=unit_system.source_refs,
                    expected="an explicitly confirmed model unit system",
                    observed=unit_system.unit_system_id,
                )
            )

        for parameter in parameters:
            record, parameter_findings = self._audit_parameter(
                parameter,
                unit_system,
            )
            if record is not None:
                records.append(record)
            findings.extend(parameter_findings)

        for equation in equations:
            findings.extend(self._audit_equation(equation))

        for scaling in derivative_scaling:
            finding = self._audit_derivative_scaling(scaling)
            if finding is not None:
                findings.append(finding)

        return PhysicalAuditReport(
            report_id=report_id,
            unit_system_id=unit_system.unit_system_id,
            status=_aggregate_status(findings),
            parameter_records=tuple(records),
            findings=tuple(findings),
            source_files_unchanged=True,
        )

    def _audit_parameter(
        self,
        parameter: PhysicalParameterInput,
        unit_system: UnitSystemContract,
    ) -> tuple[PhysicalParameterRecord | None, tuple[AuditFinding, ...]]:
        declared_unit = unit_system.quantity_units.get(parameter.quantity_kind)
        if declared_unit is None:
            finding = AuditFinding(
                code="UNIT_SYSTEM_QUANTITY_UNDECLARED",
                status=AuditStatus.NEEDS_UNIT_CONFIRMATION,
                message=(
                    f"{parameter.parameter_id} has no unit for quantity kind "
                    f"{parameter.quantity_kind} in the model unit system."
                ),
                parameter_ids=(parameter.parameter_id,),
                source_refs=(parameter.source_ref, *unit_system.source_refs),
                expected=f"declared unit for {parameter.quantity_kind}",
                observed="<missing>",
            )
            return None, (finding,)

        if parameter.raw_unit is None or not parameter.raw_unit.strip():
            finding = AuditFinding(
                code="MISSING_UNIT",
                status=AuditStatus.NEEDS_UNIT_CONFIRMATION,
                message=(
                    f"{parameter.parameter_id} has no uniquely established raw unit."
                ),
                parameter_ids=(parameter.parameter_id,),
                source_refs=(parameter.source_ref,),
                expected=declared_unit,
                observed="<missing>",
            )
            return None, (finding,)

        raw_unit = normalize_unit_text(parameter.raw_unit)
        canonical_unit = normalize_unit_text(declared_unit)
        findings: list[AuditFinding] = []

        try:
            raw_quantity = self._registry.Quantity(parameter.raw_value, raw_unit)
            canonical_quantity = raw_quantity.to(canonical_unit)
            zero = self._registry.Quantity(0.0, raw_unit).to(canonical_unit).magnitude
            one = self._registry.Quantity(1.0, raw_unit).to(canonical_unit).magnitude
        except DimensionalityError as error:
            finding = AuditFinding(
                code="DIMENSION_MISMATCH",
                status=AuditStatus.REJECT,
                message=f"{parameter.parameter_id} cannot convert to its canonical unit.",
                parameter_ids=(parameter.parameter_id,),
                source_refs=(parameter.source_ref, *parameter.use_sites),
                expected=declared_unit,
                observed=f"{parameter.raw_value} {parameter.raw_unit}: {error}",
            )
            return None, (finding,)
        except PintError as error:
            finding = AuditFinding(
                code="UNPARSEABLE_UNIT",
                status=AuditStatus.NEEDS_UNIT_CONFIRMATION,
                message=(
                    f"{parameter.parameter_id} uses an unrecognized raw or "
                    "model-canonical unit."
                ),
                parameter_ids=(parameter.parameter_id,),
                source_refs=(parameter.source_ref,),
                expected=declared_unit,
                observed=f"{parameter.raw_unit}: {error}",
            )
            return None, (finding,)

        expected_factor = float(one - zero)
        expected_offset = float(zero)

        semantic_finding = self._semantic_check(
            parameter,
            raw_unit=raw_unit,
            canonical_unit=canonical_unit,
        )
        if semantic_finding is not None:
            findings.append(semantic_finding)

        conversion_finding = self._conversion_chain_check(
            parameter,
            expected_factor=expected_factor,
            expected_offset=expected_offset,
        )
        if conversion_finding is not None:
            findings.append(conversion_finding)

        canonical_value = float(canonical_quantity.magnitude)
        if (
            parameter.plausible_min is not None
            and canonical_value < parameter.plausible_min
        ) or (
            parameter.plausible_max is not None
            and canonical_value > parameter.plausible_max
        ):
            findings.append(
                AuditFinding(
                    code="MAGNITUDE_OUTLIER",
                    status=AuditStatus.WARN,
                    message=(
                        f"{parameter.parameter_id} is outside the declared plausible "
                        "range; no replacement value was fabricated."
                    ),
                    parameter_ids=(parameter.parameter_id,),
                    source_refs=(parameter.source_ref,),
                    expected=(
                        f"[{parameter.plausible_min}, {parameter.plausible_max}] "
                        f"{declared_unit}"
                    ),
                    observed=f"{canonical_value} {declared_unit}",
                )
            )

        parameter_status = _aggregate_status(findings)
        record = PhysicalParameterRecord(
            parameter_id=parameter.parameter_id,
            symbol=parameter.symbol,
            meaning=parameter.meaning,
            quantity_kind=parameter.quantity_kind,
            unit_system_id=unit_system.unit_system_id,
            raw_value=parameter.raw_value,
            raw_unit=parameter.raw_unit,
            canonical_value=canonical_value,
            canonical_unit=declared_unit,
            dimensional_signature=str(raw_quantity.dimensionality),
            conversion_factor=expected_factor,
            conversion_offset=expected_offset,
            source_ref=parameter.source_ref,
            load_sites=parameter.load_sites,
            use_sites=parameter.use_sites,
            conversion_steps=parameter.conversion_steps,
            confirmation_status=parameter_status,
        )
        return record, tuple(findings)

    def _conversion_chain_check(
        self,
        parameter: PhysicalParameterInput,
        *,
        expected_factor: float,
        expected_offset: float,
    ) -> AuditFinding | None:
        observed_factor, observed_offset = _compose_conversion_steps(parameter)
        conversion_required = not (
            _close(expected_factor, 1.0, self._relative_tolerance)
            and _close(expected_offset, 0.0, self._relative_tolerance)
        )

        if parameter.consumption is ParameterConsumption.DERIVED_MANIFEST:
            if parameter.conversion_steps and conversion_required:
                return AuditFinding(
                    code="DUPLICATE_CONVERSION_RISK",
                    status=AuditStatus.REJECT,
                    message=(
                        f"{parameter.parameter_id} declares existing code conversion "
                        "while the canonical derived manifest would also convert it."
                    ),
                    parameter_ids=(parameter.parameter_id,),
                    source_refs=(
                        parameter.source_ref,
                        *(step.source_ref for step in parameter.conversion_steps),
                    ),
                    expected="canonical manifest conversion only",
                    observed=_format_affine(observed_factor, observed_offset),
                )
            return None

        if conversion_required and not parameter.conversion_steps:
            return AuditFinding(
                code="MISSING_CONVERSION",
                status=AuditStatus.REJECT,
                message=(
                    f"{parameter.parameter_id} reaches a raw code path without the "
                    "required canonical conversion."
                ),
                parameter_ids=(parameter.parameter_id,),
                source_refs=(parameter.source_ref, *parameter.use_sites),
                expected=_format_affine(expected_factor, expected_offset),
                observed=_format_affine(1.0, 0.0),
            )

        if not (
            _close(observed_factor, expected_factor, self._relative_tolerance)
            and _close(observed_offset, expected_offset, self._relative_tolerance)
        ):
            return AuditFinding(
                code="CONVERSION_CHAIN_MISMATCH",
                status=AuditStatus.REJECT,
                message=(
                    f"{parameter.parameter_id} has a missing, duplicate or incorrect "
                    "conversion chain."
                ),
                parameter_ids=(parameter.parameter_id,),
                source_refs=(
                    parameter.source_ref,
                    *(step.source_ref for step in parameter.conversion_steps),
                ),
                expected=_format_affine(expected_factor, expected_offset),
                observed=_format_affine(observed_factor, observed_offset),
            )
        return None

    def _semantic_check(
        self,
        parameter: PhysicalParameterInput,
        *,
        raw_unit: str,
        canonical_unit: str,
    ) -> AuditFinding | None:
        tags = {tag.casefold() for tag in parameter.semantic_tags}
        raw_lower = raw_unit.casefold()
        canonical_lower = canonical_unit.casefold()

        if "angular_frequency" in tags and (
            "hz" in raw_lower or "hertz" in raw_lower
        ) and ("radian" in canonical_lower or "rad/" in canonical_lower):
            has_two_pi = any(
                _close(abs(step.factor), 2.0 * math.pi, 1e-6)
                for step in parameter.conversion_steps
            )
            if not has_two_pi:
                return AuditFinding(
                    code="FREQUENCY_SEMANTIC_AMBIGUITY",
                    status=AuditStatus.NEEDS_UNIT_CONFIRMATION,
                    message=(
                        "Frequency and angular frequency share dimensions but require "
                        "an explicit 2*pi semantic conversion."
                    ),
                    parameter_ids=(parameter.parameter_id,),
                    source_refs=(parameter.source_ref, *parameter.use_sites),
                    expected="explicit frequency-to-angular-frequency conversion",
                    observed=parameter.raw_unit,
                )

        if (
            "absolute_temperature_required" in tags
            and ("degc" in raw_lower or "celsius" in raw_lower)
            and parameter.consumption is ParameterConsumption.RAW_CODE_PATH
            and not parameter.conversion_steps
        ):
            return AuditFinding(
                code="ABSOLUTE_TEMPERATURE_REQUIRED",
                status=AuditStatus.REJECT,
                message=(
                    "Celsius cannot be used directly where an absolute temperature "
                    "expression such as radiation T^4 is evaluated."
                ),
                parameter_ids=(parameter.parameter_id,),
                source_refs=(parameter.source_ref, *parameter.use_sites),
                expected="explicit conversion to kelvin before use",
                observed=parameter.raw_unit,
            )
        return None

    def _audit_equation(
        self,
        equation: EquationAuditSpec,
    ) -> tuple[AuditFinding, ...]:
        dimensions: list[tuple[str, str]] = []
        for term in equation.additive_terms:
            try:
                dimensionality = str(
                    self._registry.Unit(normalize_unit_text(term.unit)).dimensionality
                )
            except PintError as error:
                return (
                    AuditFinding(
                        code="EQUATION_UNIT_UNPARSEABLE",
                        status=AuditStatus.NEEDS_UNIT_CONFIRMATION,
                        message=f"{equation.equation_id} contains an unparseable term.",
                        source_refs=(term.source_ref,),
                        expected="a parseable physical unit",
                        observed=f"{term.unit}: {error}",
                    ),
                )
            dimensions.append((term.term_id, dimensionality))

        expected = dimensions[0][1]
        mismatched = [item for item in dimensions[1:] if item[1] != expected]
        if not mismatched:
            return ()
        return (
            AuditFinding(
                code="ADDITIVE_TERM_DIMENSION_MISMATCH",
                status=AuditStatus.REJECT,
                message=(
                    f"{equation.equation_id} has additive {equation.equation_kind} "
                    "terms with incompatible dimensions."
                ),
                source_refs=tuple(term.source_ref for term in equation.additive_terms),
                expected=f"{equation.additive_terms[0].term_id}: {expected}",
                observed=", ".join(f"{name}: {dim}" for name, dim in mismatched),
            ),
        )

    def _audit_derivative_scaling(
        self,
        scaling: DerivativeScalingSpec,
    ) -> AuditFinding | None:
        expected = scaling.output_scale / (
            scaling.coordinate_scale**scaling.derivative_order
        )
        if _close(scaling.observed_factor, expected, self._relative_tolerance):
            return None
        return AuditFinding(
            code="DERIVATIVE_CHAIN_RULE_MISMATCH",
            status=AuditStatus.REJECT,
            message=(
                f"{scaling.check_id} has an incorrect order-"
                f"{scaling.derivative_order} chain-rule factor."
            ),
            source_refs=(scaling.source_ref,),
            expected=str(expected),
            observed=str(scaling.observed_factor),
        )


def normalize_unit_text(unit: str) -> str:
    """Normalize common scientific typography without guessing missing units."""

    normalized = unit.strip()
    replacements = (
        ("℃", "degC"),
        ("°C", "degC"),
        ("·", "*"),
        ("⋅", "*"),
        ("²", "**2"),
        ("³", "**3"),
        ("^", "**"),
    )
    for source, target in replacements:
        normalized = normalized.replace(source, target)
    return normalized


def _compose_conversion_steps(
    parameter: PhysicalParameterInput,
) -> tuple[float, float]:
    factor = 1.0
    offset = 0.0
    for step in parameter.conversion_steps:
        factor = factor * step.factor
        offset = offset * step.factor + step.offset
    return factor, offset


def _aggregate_status(findings: Iterable[AuditFinding]) -> AuditStatus:
    statuses = {finding.status for finding in findings}
    for status in (
        AuditStatus.REJECT,
        AuditStatus.NEEDS_UNIT_CONFIRMATION,
        AuditStatus.NEEDS_EVIDENCE,
        AuditStatus.WARN,
    ):
        if status in statuses:
            return status
    return AuditStatus.PASS


def _close(left: float, right: float, relative_tolerance: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=relative_tolerance,
        abs_tol=relative_tolerance,
    )


def _format_affine(factor: float, offset: float) -> str:
    return f"value * {factor} + {offset}"

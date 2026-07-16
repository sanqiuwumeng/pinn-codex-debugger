from __future__ import annotations

import hashlib
import math
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.assurance import PhysicalAuditService  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    AuditStatus,
    ConversionStep,
    DerivativeScalingSpec,
    EquationAuditSpec,
    EquationTermSpec,
    ParameterConsumption,
    PhysicalParameterInput,
    SourceRef,
    UnitSystemContract,
)

SHA = "c" * 64


def source(symbol: str = "value") -> SourceRef:
    return SourceRef(
        uri="file:///project/config.json",
        sha256=SHA,
        line_start=1,
        line_end=1,
        symbol=symbol,
    )


def parameter(
    parameter_id: str,
    value: float,
    raw_unit: str | None,
    **kwargs,
) -> PhysicalParameterInput:
    return PhysicalParameterInput(
        parameter_id=parameter_id,
        symbol=parameter_id,
        meaning=parameter_id.replace("_", " "),
        quantity_kind=parameter_id,
        raw_value=value,
        raw_unit=raw_unit,
        source_ref=source(parameter_id),
        **kwargs,
    )


def unit_system(**quantity_units: str) -> UnitSystemContract:
    return UnitSystemContract(
        unit_system_id="model-units",
        name="model-declared units",
        quantity_units=quantity_units,
        source_refs=(source("unit-system"),),
        confirmed_by_user=True,
    )


class PhysicalAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.auditor = PhysicalAuditService()

    def test_mass_density_heat_capacity_length_time_and_sources_convert(self) -> None:
        cases = (
            ("mass", 1000.0, "g", "kg", 1.0),
            ("density", 4.43, "g/cm³", "kg/m^3", 4430.0),
            ("specific_heat", 0.526, "J/(g*K)", "J/(kg*K)", 526.0),
            ("length", 5.0, "mm", "m", 0.005),
            ("time", 2.0, "ms", "s", 0.002),
            ("heat_flux", 1.5, "W/mm²", "W/m^2", 1.5e6),
            ("volume_source", 2.0, "W/mm³", "W/m^3", 2.0e9),
        )
        inputs = tuple(
            parameter(name, value, raw)
            for name, value, raw, _, _ in cases
        )
        report = self.auditor.audit(
            report_id="units",
            unit_system=unit_system(
                **{name: canonical for name, _, _, canonical, _ in cases}
            ),
            parameters=inputs,
        )

        self.assertEqual(report.status, AuditStatus.PASS)
        actual = {
            record.parameter_id: record.canonical_value
            for record in report.parameter_records
        }
        for name, _, _, _, expected in cases:
            self.assertTrue(
                math.isclose(actual[name], expected, rel_tol=1e-12, abs_tol=1e-12),
                f"{name}: expected {expected}, observed {actual[name]}",
            )

    def test_missing_unit_requests_confirmation_without_guessing(self) -> None:
        report = self.auditor.audit(
            report_id="missing-unit",
            unit_system=unit_system(conductivity="W/(m*K)"),
            parameters=(parameter("conductivity", 7.2, None),),
        )
        self.assertEqual(report.status, AuditStatus.NEEDS_UNIT_CONFIRMATION)
        self.assertEqual(report.findings[0].code, "MISSING_UNIT")
        self.assertFalse(report.parameter_records)

    def test_surface_source_cannot_fill_volumetric_source_term(self) -> None:
        report = self.auditor.audit(
            report_id="source-dimensionality",
            unit_system=unit_system(source="W/m^3"),
            parameters=(
                parameter("source", 10.0, "W/m^2"),
            ),
        )
        self.assertEqual(report.status, AuditStatus.REJECT)
        self.assertEqual(report.findings[0].code, "DIMENSION_MISMATCH")

    def test_raw_code_path_detects_missing_and_duplicate_conversion(self) -> None:
        missing = parameter(
            "density",
            4.43,
            "g/cm^3",
            consumption=ParameterConsumption.RAW_CODE_PATH,
            use_sites=(source("pde-density"),),
        )
        duplicate = parameter(
            "heat_flux",
            1.0,
            "W/mm^2",
            consumption=ParameterConsumption.RAW_CODE_PATH,
            conversion_steps=(
                ConversionStep(
                    operation="first conversion",
                    factor=1e6,
                    apply_site="load",
                    source_ref=source("load"),
                ),
                ConversionStep(
                    operation="duplicate conversion",
                    factor=1e6,
                    apply_site="boundary",
                    source_ref=source("boundary"),
                ),
            ),
        )
        report = self.auditor.audit(
            report_id="conversion-chain",
            unit_system=unit_system(
                density="kg/m^3",
                heat_flux="W/m^2",
            ),
            parameters=(missing, duplicate),
        )
        self.assertEqual(report.status, AuditStatus.REJECT)
        self.assertEqual(
            {finding.code for finding in report.findings},
            {"MISSING_CONVERSION", "CONVERSION_CHAIN_MISMATCH"},
        )

    def test_celsius_directly_used_in_radiation_is_rejected(self) -> None:
        report = self.auditor.audit(
            report_id="absolute-temperature",
            unit_system=unit_system(surface_temperature="K"),
            parameters=(
                parameter(
                    "surface_temperature",
                    25.0,
                    "°C",
                    consumption=ParameterConsumption.RAW_CODE_PATH,
                    semantic_tags=("absolute_temperature_required",),
                    use_sites=(source("radiation-t4"),),
                ),
            ),
        )
        self.assertEqual(report.status, AuditStatus.REJECT)
        codes = {finding.code for finding in report.findings}
        self.assertIn("ABSOLUTE_TEMPERATURE_REQUIRED", codes)
        self.assertIn("MISSING_CONVERSION", codes)

    def test_frequency_and_angular_frequency_require_semantic_confirmation(self) -> None:
        report = self.auditor.audit(
            report_id="angular-frequency",
            unit_system=unit_system(omega="radian/second"),
            parameters=(
                parameter(
                    "omega",
                    10.0,
                    "Hz",
                    semantic_tags=("angular_frequency",),
                ),
            ),
        )
        self.assertEqual(report.status, AuditStatus.NEEDS_UNIT_CONFIRMATION)
        self.assertEqual(
            report.findings[0].code,
            "FREQUENCY_SEMANTIC_AMBIGUITY",
        )

    def test_equation_additive_terms_require_matching_dimensions(self) -> None:
        equation = EquationAuditSpec(
            equation_id="heat-pde",
            equation_kind="PDE",
            additive_terms=(
                EquationTermSpec(
                    term_id="storage",
                    unit="W/m^3",
                    source_ref=source("storage"),
                ),
                EquationTermSpec(
                    term_id="wrong-source",
                    unit="W/m^2",
                    source_ref=source("source"),
                ),
            ),
        )
        report = self.auditor.audit(
            report_id="equation",
            unit_system=unit_system(length="mm"),
            parameters=(),
            equations=(equation,),
        )
        self.assertEqual(report.status, AuditStatus.REJECT)
        self.assertEqual(
            report.findings[0].code,
            "ADDITIVE_TERM_DIMENSION_MISMATCH",
        )

    def test_first_second_and_time_derivative_scaling(self) -> None:
        checks = (
            DerivativeScalingSpec(
                check_id="dx",
                coordinate="x_hat",
                derivative_order=1,
                coordinate_scale=0.01,
                output_scale=1000.0,
                observed_factor=100000.0,
                source_ref=source("dx"),
            ),
            DerivativeScalingSpec(
                check_id="dxx",
                coordinate="x_hat",
                derivative_order=2,
                coordinate_scale=0.01,
                output_scale=1000.0,
                observed_factor=10_000_000.0,
                source_ref=source("dxx"),
            ),
            DerivativeScalingSpec(
                check_id="dt-wrong",
                coordinate="t_hat",
                derivative_order=1,
                coordinate_scale=0.001,
                output_scale=1000.0,
                observed_factor=1000.0,
                source_ref=source("dt"),
            ),
        )
        report = self.auditor.audit(
            report_id="derivatives",
            unit_system=unit_system(length="mm"),
            parameters=(),
            derivative_scaling=checks,
        )
        self.assertEqual(report.status, AuditStatus.REJECT)
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(
            report.findings[0].code,
            "DERIVATIVE_CHAIN_RULE_MISMATCH",
        )

    def test_audit_never_changes_the_source_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "physics.json"
            original = b'{"density": {"value": 4.43, "unit": "g/cm^3"}}\n'
            config.write_bytes(original)
            before = hashlib.sha256(config.read_bytes()).hexdigest()

            report = self.auditor.audit(
                report_id="no-overwrite",
                unit_system=unit_system(density="kg/m^3"),
                parameters=(parameter("density", 4.43, "g/cm^3"),),
            )

            after = hashlib.sha256(config.read_bytes()).hexdigest()
            self.assertEqual(report.status, AuditStatus.PASS)
            self.assertTrue(report.source_files_unchanged)
            self.assertEqual(before, after)
            self.assertEqual(config.read_bytes(), original)

    def test_declared_mm_model_accepts_explicit_metre_conversion(self) -> None:
        report = self.auditor.audit(
            report_id="mixed-length-with-conversion",
            unit_system=unit_system(length="mm"),
            parameters=(
                PhysicalParameterInput(
                    parameter_id="domain_length",
                    symbol="L",
                    meaning="domain length",
                    quantity_kind="length",
                    raw_value=0.1,
                    raw_unit="m",
                    source_ref=source("domain-length"),
                ),
                PhysicalParameterInput(
                    parameter_id="source_radius",
                    symbol="r",
                    meaning="source radius",
                    quantity_kind="length",
                    raw_value=2.5,
                    raw_unit="mm",
                    source_ref=source("source-radius"),
                ),
            ),
        )

        self.assertEqual(report.status, AuditStatus.PASS)
        canonical = {
            record.parameter_id: record.canonical_value
            for record in report.parameter_records
        }
        self.assertEqual(canonical, {"domain_length": 100.0, "source_radius": 2.5})

    def test_declared_mm_model_rejects_unconverted_metre_raw_path(self) -> None:
        report = self.auditor.audit(
            report_id="mixed-length-without-conversion",
            unit_system=unit_system(length="mm"),
            parameters=(
                PhysicalParameterInput(
                    parameter_id="domain_length",
                    symbol="L",
                    meaning="domain length",
                    quantity_kind="length",
                    raw_value=0.1,
                    raw_unit="m",
                    source_ref=source("domain-length"),
                    use_sites=(source("pde-coordinate"),),
                    consumption=ParameterConsumption.RAW_CODE_PATH,
                ),
            ),
        )

        self.assertEqual(report.status, AuditStatus.REJECT)
        self.assertEqual(report.findings[0].code, "MISSING_CONVERSION")


if __name__ == "__main__":
    unittest.main()

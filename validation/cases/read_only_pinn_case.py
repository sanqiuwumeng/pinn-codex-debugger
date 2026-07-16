"""Read-only audit of existing PINN/FEM artifacts; never starts training."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
sys.path.insert(0, str(ORCHESTRATOR_SRC))

from pinn_strategy_system.assurance import (  # noqa: E402
    EvaluationBasisService,
    MetricDecisionService,
    PhysicalAuditService,
)
from pinn_strategy_system.contracts import (  # noqa: E402
    AggregationPolicy,
    ArtifactRef,
    AuditStatus,
    MetricContract,
    MetricDirection,
    MetricEvidenceBasis,
    MetricRole,
    MetricRule,
    MetricValueSet,
    ParameterConsumption,
    PhysicalParameterInput,
    PhysicalModelAuthority,
    ReferenceEvidence,
    ReferenceKind,
    ResultStatus,
    SourceRef,
    UnitSystemContract,
)
from pinn_strategy_system.domain_metrics.heat_transfer import (  # noqa: E402
    HeatTransferPhaseConfig,
    HeatTransferPhaseMetricProvider,
)
from pinn_strategy_system.execution import (  # noqa: E402
    FieldData,
    PredictionAnalyzer,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(artifact_id: str, path: Path) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        uri=path.as_uri(),
        sha256=_sha256(path),
        size_bytes=path.stat().st_size,
    )


def _snapshot(paths: tuple[Path, ...]) -> dict[str, str]:
    return {
        str(path.resolve(strict=True)): _sha256(path)
        for path in paths
    }


def _get(payload: dict[str, Any], pointer: tuple[str, ...]) -> float:
    value: Any = payload
    for component in pointer:
        value = value[component]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"physical value is not numeric: {pointer}")
    return float(value)


def _physical_inputs(
    *,
    config: dict[str, Any],
    config_path: Path,
    config_code: Path,
    physics_code: Path,
) -> tuple[PhysicalParameterInput, ...]:
    source_hash = _sha256(config_path)
    config_hash = _sha256(config_code)
    physics_hash = _sha256(physics_code)
    specs = (
        ("density", ("scenario", "material", "rho"), "density", "kg/m^3"),
        (
            "specific_heat",
            ("scenario", "material", "cp"),
            "specific_heat",
            "J/(kg*K)",
        ),
        (
            "conductivity",
            ("scenario", "material", "conductivity"),
            "conductivity",
            "W/(m*K)",
        ),
        (
            "latent_heat",
            ("scenario", "material", "latent_heat"),
            "latent_heat",
            "J/kg",
        ),
        ("solidus", ("scenario", "material", "solidus"), "temperature", "K"),
        ("liquidus", ("scenario", "material", "liquidus"), "temperature", "K"),
        (
            "initial_temperature",
            ("scenario", "initial_temperature"),
            "temperature",
            "K",
        ),
        (
            "peak_temperature",
            ("scenario", "peak_temperature"),
            "temperature",
            "K",
        ),
        ("ramp_time", ("scenario", "ramp_time"), "time", "s"),
        ("x_min", ("scenario", "x_min"), "length", "m"),
        ("x_max", ("scenario", "x_max"), "length", "m"),
        ("y_min", ("scenario", "y_min"), "length", "m"),
        ("y_max", ("scenario", "y_max"), "length", "m"),
        ("t_min", ("scenario", "t_min"), "time", "s"),
        ("t_max", ("scenario", "t_max"), "time", "s"),
    )
    return tuple(
        PhysicalParameterInput(
            parameter_id=name,
            symbol=name,
            meaning=name.replace("_", " "),
            quantity_kind=quantity_kind,
            raw_value=_get(config, pointer),
            raw_unit=raw_unit,
            source_ref=SourceRef(
                uri=config_path.as_uri(),
                sha256=source_hash,
                symbol="json-pointer:/" + "/".join(pointer),
            ),
            load_sites=(
                SourceRef(
                    uri=config_code.as_uri(),
                    sha256=config_hash,
                    symbol=name,
                ),
            ),
            use_sites=(
                SourceRef(
                    uri=physics_code.as_uri(),
                    sha256=physics_hash,
                    symbol="PINN/FEM shared physics",
                ),
            ),
            consumption=ParameterConsumption.RAW_CODE_PATH,
            semantic_tags=(
                ("absolute_temperature_required",)
                if "temperature" in name or name in {"solidus", "liquidus"}
                else ()
            ),
        )
        for name, pointer, quantity_kind, raw_unit in specs
    )


def _confirmed_case_unit_system(config_path: Path) -> UnitSystemContract:
    approval_path = (
        REPOSITORY_ROOT
        / "openspec"
        / "changes"
        / "build-rag-multi-agent-dl-strategy-system"
        / "approval-records"
        / "2026-07-16-universal-pinn-architecture.md"
    )
    return UnitSystemContract(
        unit_system_id="pinn-2d-test-case-si",
        name="User-confirmed SI units for the PINN-2D validation case",
        quantity_units={
            "density": "kg/m^3",
            "specific_heat": "J/(kg*K)",
            "conductivity": "W/(m*K)",
            "latent_heat": "J/kg",
            "temperature": "K",
            "length": "m",
            "time": "s",
        },
        source_refs=(
            SourceRef(
                uri=approval_path.as_uri(),
                sha256=_sha256(approval_path),
                symbol="user-confirmed case unit contract",
            ),
            SourceRef(
                uri=config_path.as_uri(),
                sha256=_sha256(config_path),
                symbol="case parameter values",
            ),
        ),
        confirmed_by_user=True,
    )


def _field(
    *,
    values: np.ndarray,
    artifact_ref: ArtifactRef,
    arrays: Any,
    reference_identity: str,
) -> FieldData:
    return FieldData(
        values=values,
        artifact_ref=artifact_ref,
        axes=("t", "y", "x"),
        coordinates={
            "t": arrays["t"],
            "y": arrays["y"],
            "x": arrays["x"],
        },
        reference_identity=reference_identity,
        unit="K",
        coordinate_system="cartesian",
        normalization="physical",
    )


def run_case(
    *,
    case_root: Path,
    baseline_name: str,
    candidate_name: str,
) -> dict[str, Any]:
    if not case_root.is_absolute():
        raise ValueError("case_root must be absolute")
    case_root = case_root.resolve(strict=True)
    baseline_root = case_root / "outputs" / baseline_name
    candidate_root = case_root / "outputs" / candidate_name
    config_path = baseline_root / "benchmark_config.json"
    candidate_config_path = candidate_root / "benchmark_config.json"
    baseline_fields_path = baseline_root / "data" / "aligned_fields.npz"
    candidate_fields_path = candidate_root / "data" / "aligned_fields.npz"
    config_code = case_root / "config.py"
    physics_code = case_root / "physics.py"
    runner_code = case_root / "run_benchmark.py"
    observed_paths = (
        config_code,
        physics_code,
        runner_code,
        config_path,
        candidate_config_path,
        baseline_root / "field_metrics.json",
        candidate_root / "field_metrics.json",
        baseline_fields_path,
        candidate_fields_path,
    )
    before = _snapshot(observed_paths)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    candidate_config = json.loads(
        candidate_config_path.read_text(encoding="utf-8")
    )
    case_unit_system = _confirmed_case_unit_system(config_path)
    case_authority = PhysicalModelAuthority(
        authority_id="pinn-2d-user-model",
        project_id="pinn-2d-validation-case",
        model_family="pinn",
        pde_family="transient-heat-equation-with-phase-change",
        task_type="forward",
        governing_equation_refs=(
            SourceRef(
                uri=physics_code.as_uri(),
                sha256=_sha256(physics_code),
                symbol="shared PINN/FEM governing physics",
            ),
        ),
        boundary_condition_refs=(
            SourceRef(
                uri=physics_code.as_uri(),
                sha256=_sha256(physics_code),
                symbol="boundary conditions",
            ),
        ),
        initial_condition_refs=(
            SourceRef(
                uri=physics_code.as_uri(),
                sha256=_sha256(physics_code),
                symbol="initial condition",
            ),
        ),
        geometry_refs=(
            SourceRef(
                uri=config_path.as_uri(),
                sha256=_sha256(config_path),
                symbol="json-pointer:/scenario",
            ),
        ),
        parameter_source_refs=(
            SourceRef(
                uri=config_path.as_uri(),
                sha256=_sha256(config_path),
                symbol="json-pointer:/scenario/material",
            ),
        ),
        output_channels=("temperature",),
        unit_system=case_unit_system,
        confirmed_by_user=True,
    )
    physical_report = PhysicalAuditService().audit(
        report_id="readonly-pinn-physical-preflight",
        unit_system=case_unit_system,
        parameters=_physical_inputs(
            config=config,
            config_path=config_path,
            config_code=config_code,
            physics_code=physics_code,
        ),
    )

    with np.load(baseline_fields_path, allow_pickle=False) as baseline_arrays:
        with np.load(
            candidate_fields_path,
            allow_pickle=False,
        ) as candidate_arrays:
            reference = np.asarray(baseline_arrays["fem"])
            reference_identity = hashlib.sha256(
                reference.tobytes()
            ).hexdigest()
            baseline_ref = _artifact(
                "readonly-baseline-aligned-fields",
                baseline_fields_path,
            )
            candidate_ref = _artifact(
                "readonly-candidate-aligned-fields",
                candidate_fields_path,
            )
            baseline_field = _field(
                values=np.asarray(baseline_arrays["pinn"]),
                artifact_ref=baseline_ref,
                arrays=baseline_arrays,
                reference_identity=reference_identity,
            )
            candidate_field = _field(
                values=np.asarray(candidate_arrays["pinn"]),
                artifact_ref=candidate_ref,
                arrays=candidate_arrays,
                reference_identity=reference_identity,
            )
            reference_field = _field(
                values=reference,
                artifact_ref=baseline_ref,
                arrays=baseline_arrays,
                reference_identity=reference_identity,
            )
            t_grid, y_grid, x_grid = np.meshgrid(
                baseline_arrays["t"],
                baseline_arrays["y"],
                baseline_arrays["x"],
                indexing="ij",
            )
            roi_masks = {
                "early_top_center": (
                    (np.abs(x_grid) <= 0.01)
                    & (y_grid >= 0.075)
                    & (t_grid <= 10.0)
                )
            }
            material = config["scenario"]["material"]
            comparison = PredictionAnalyzer().compare(
                report_id="readonly-pinn-field-comparison",
                baseline=baseline_field,
                candidate=candidate_field,
                reference=reference_field,
                top_k=5,
                roi_masks=roi_masks,
                domain_metric_providers=(
                    HeatTransferPhaseMetricProvider(
                        HeatTransferPhaseConfig(
                            solidus=float(material["solidus"]),
                            liquidus=float(material["liquidus"]),
                            threshold_band=10.0,
                        )
                    ),
                ),
            )
            fem_fields_match = bool(
                np.array_equal(
                    baseline_arrays["fem"],
                    candidate_arrays["fem"],
                )
            )

    baseline_metrics = comparison.baseline_report.global_metrics
    candidate_metrics = comparison.candidate_report.global_metrics
    case_reference = ReferenceEvidence(
        reference_id="pinn-2d-fine-fem-test-reference",
        authority_id=case_authority.authority_id,
        kind=ReferenceKind.NUMERICAL,
        artifact_ref=_artifact(
            "pinn-2d-fem-test-reference",
            baseline_fields_path,
        ),
        output_channels=("temperature",),
        coordinate_system="cartesian",
        channel_units={"temperature": "K"},
        source_refs=(
            SourceRef(
                uri=runner_code.as_uri(),
                sha256=_sha256(runner_code),
                symbol="fine FEM reference selection",
            ),
        ),
        test_case_only=True,
        limitations=(
            "Numerical validation reference for this PINN-2D case only.",
        ),
    )
    basis_result = EvaluationBasisService().validate(
        authority=case_authority,
        references=(case_reference,),
    )
    case_metric_contract = MetricContract(
        contract_id="pinn-2d-user-confirmed-2026-07-16",
        physical_model_authority_ref=_artifact(
            "pinn-2d-physical-model-authority",
            physics_code,
        ),
        reference_evidence_refs=(
            case_reference.artifact_ref,
        ),
        metrics=(
            MetricRule(
                name="max_abs",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="K",
            ),
            MetricRule(
                name="rmse",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="K",
            ),
            MetricRule(
                name="mae",
                role=MetricRole.GUARDRAIL,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                max_regression=1.0,
                max_relative_regression=0.10,
                unit="K",
            ),
        ),
        primary_order=("max_abs", "rmse"),
        aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
        acceptable_regression_notes=(
            "MAE must regress by no more than 1.0 K and 10 percent.",
        ),
    )
    decision = MetricDecisionService().compare(
        decision_id="readonly-pinn-metric-gate",
        contract=(
            case_metric_contract
            if physical_report.status is AuditStatus.PASS
            and comparison.status is ResultStatus.VALID
            and basis_result.ready
            else None
        ),
        baseline=MetricValueSet(
            subject_id=baseline_name,
            values=baseline_metrics,
        ),
        candidate=MetricValueSet(
            subject_id=candidate_name,
            values=candidate_metrics,
        ),
        observed_failure_mechanism=(
            "localized reference-backed error in the PINN-2D validation case"
        ),
    )
    after = _snapshot(observed_paths)
    return {
        "case_root": str(case_root),
        "baseline": baseline_name,
        "candidate": candidate_name,
        "read_only": {
            "source_hashes_before": before,
            "source_hashes_after": after,
            "all_observed_sources_unchanged": before == after,
        },
        "config_identity": {
            "baseline_equals_candidate": config == candidate_config,
            "reference_fem_fields_equal": fem_fields_match,
        },
        "physical_audit": {
            "status": physical_report.status.value,
            "missing_unit_parameters": [
                finding.parameter_ids[0]
                for finding in physical_report.findings
                if finding.code == "MISSING_UNIT"
            ],
            "findings": [
                finding.model_dump(mode="json")
                for finding in physical_report.findings
            ],
            "source_files_unchanged": physical_report.source_files_unchanged,
        },
        "prediction_analysis": {
            "status": comparison.status.value,
            "baseline_global_metrics": baseline_metrics,
            "candidate_global_metrics": candidate_metrics,
            "metric_deltas_candidate_minus_baseline": comparison.metric_deltas,
            "baseline_max_abs": (
                comparison.baseline_report.max_abs.model_dump(mode="json")
                if comparison.baseline_report.max_abs
                else None
            ),
            "candidate_max_abs": (
                comparison.candidate_report.max_abs.model_dump(mode="json")
                if comparison.candidate_report.max_abs
                else None
            ),
            "baseline_roi_metrics": comparison.baseline_report.roi_metrics,
            "candidate_roi_metrics": comparison.candidate_report.roi_metrics,
            "baseline_domain_metrics": (
                comparison.baseline_report.domain_metrics
            ),
            "candidate_domain_metrics": (
                comparison.candidate_report.domain_metrics
            ),
            "error_migrated": comparison.error_migrated,
            "findings": list(comparison.findings),
        },
        "metric_gate": {
            "user_metric_contract_present": True,
            "contract": case_metric_contract.model_dump(mode="json"),
            "status": decision.status.value,
            "reasons": list(decision.reasons),
            "selected_intervention": decision.selected_intervention,
        },
        "case_scope": {
            "physical_model_authority": case_authority.model_dump(mode="json"),
            "reference_evidence": case_reference.model_dump(mode="json"),
            "evaluation_basis": {
                "ready": basis_result.ready,
                "checks": basis_result.checks,
                "reasons": list(basis_result.reasons),
            },
            "roi_role": "case diagnostic only; not a universal default",
            "domain_provider": "heat-transfer.phase-change.v1",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--baseline", default="full")
    parser.add_argument("--candidate", default="hybrid_rag_optimized_v2")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_case(
        case_root=args.case_root,
        baseline_name=args.baseline,
        candidate_name=args.candidate,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is not None:
        output = args.output.resolve(strict=False)
        if output.exists():
            raise FileExistsError(f"refusing to overwrite output: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output)}, ensure_ascii=False))
    else:
        print(encoded)


if __name__ == "__main__":
    main()

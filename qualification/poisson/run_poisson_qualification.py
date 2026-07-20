"""Run the governed two-dimensional Poisson scientific qualification case."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
sys.path.insert(0, str(ORCHESTRATOR_SRC))
sys.path.insert(0, str(REPOSITORY_ROOT))

from pinn_strategy_system.assurance import (  # noqa: E402
    EvaluationBasisService,
    MetricDecisionService,
    PhysicalAuditService,
    RunValidationService,
)
from pinn_strategy_system.contracts import (  # noqa: E402
    AggregationPolicy,
    ApprovalKind,
    ApprovalRecord,
    ArtifactRef,
    AuditStatus,
    DecisionRecord,
    DecisionStatus,
    MetricContract,
    MetricDirection,
    MetricEvidenceBasis,
    MetricRole,
    MetricRule,
    MetricValueSet,
    ModelEvaluationReport,
    PhysicalModelAuthority,
    PhysicalParameterInput,
    ReferenceEvidence,
    ReferenceKind,
    ResultStatus,
    RunManifest,
    RunValidationInput,
    SourceRef,
    UnitSystemContract,
)
from pinn_strategy_system.domain_metrics.poisson import (  # noqa: E402
    PoissonMetricProvider,
)
from pinn_strategy_system.execution import (  # noqa: E402
    FieldData,
    ManifestFirstRunner,
    PredictionAnalyzer,
    SQLiteRunRegistry,
)
from pinn_strategy_system.storage import AppendOnlyAuditStore  # noqa: E402
from qualification.support import (  # noqa: E402
    ForbiddenReplayBackend,
    _artifact,
    _build_local_backend,
    _run_one,
    _sha256,
    _verify_artifact_reference,
    load_approval,
)

WORKFLOW_ID = "poisson-qualification-v1"
APPROVAL_SCOPE = f"qualification:{WORKFLOW_ID}"
EXPECTED_OUTPUTS = (
    "case_contract.json",
    "run_config.json",
    "runtime_environment.json",
    "training_history.json",
    "field_metrics.json",
    "aligned_fields.json",
    "model.pt",
    "reproducibility_manifest.json",
)
SEMANTIC_SCAN_TOKENS = (
    "temperature",
    "kelvin",
    "phase",
    "melt",
    "fem-default",
    "fem_default",
)


def _write_json(path: Path, payload: Any) -> ArtifactRef:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite qualification evidence: {path}")
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return _artifact(path.stem, path)


def _training_environment(training_python: Path) -> dict[str, Any]:
    probe = (
        "import json,sys,numpy,torch;"
        "print(json.dumps({'python':sys.version.split()[0],"
        "'executable':sys.executable,'torch':torch.__version__,"
        "'numpy':numpy.__version__,"
        "'cuda_available':torch.cuda.is_available()},sort_keys=True))"
    )
    completed = subprocess.run(
        (str(training_python), "-c", probe),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    environment = json.loads(completed.stdout)
    if (
        environment["python"] != "3.11.11"
        or not environment["torch"].startswith("2.3.1")
        or environment["numpy"] != "2.2.5"
    ):
        raise RuntimeError(
            "Poisson qualification requires Python 3.11.11, torch 2.3.1 and NumPy 2.2.5"
        )
    return environment


def _approved_metric_record(path: Path) -> ApprovalRecord:
    return load_approval(
        path,
        workflow_id=WORKFLOW_ID,
        kind=ApprovalKind.METRIC_PRIORITY,
        scope=APPROVAL_SCOPE,
    )


def _execution_approval(path: Path) -> ApprovalRecord:
    return load_approval(
        path,
        workflow_id=WORKFLOW_ID,
        kind=ApprovalKind.EXPERIMENT,
        scope=APPROVAL_SCOPE,
    )


def _source_ref(worker: Path, symbol: str) -> SourceRef:
    return SourceRef(uri=worker.as_uri(), sha256=_sha256(worker), symbol=symbol)


def _case_contracts(worker: Path) -> tuple[
    UnitSystemContract,
    PhysicalModelAuthority,
    ReferenceEvidence,
    MetricContract,
]:
    worker_artifact = _artifact("poisson-worker-source", worker)
    unit_system = UnitSystemContract(
        unit_system_id="poisson-unit-square-dimensionless-v1",
        name="dimensionless unit-square coordinates and scalar solution",
        quantity_units={
            "coordinate": "dimensionless",
            "solution": "dimensionless",
            "u": "dimensionless",
            "forcing": "dimensionless",
        },
        source_refs=(_source_ref(worker, "case contract"),),
        confirmed_by_user=True,
    )
    authority = PhysicalModelAuthority(
        authority_id="poisson-manufactured-authority-v1",
        project_id="universal-pinn-cross-domain-qualification",
        model_family="pinn",
        pde_family="elliptic-poisson",
        task_type="forward",
        governing_equation_refs=(_source_ref(worker, "pde_residual"),),
        boundary_condition_refs=(_source_ref(worker, "PoissonNet.forward"),),
        geometry_refs=(_source_ref(worker, "_configuration"),),
        parameter_source_refs=(_source_ref(worker, "forcing"),),
        output_channels=("u",),
        unit_system=unit_system,
        confirmed_by_user=True,
    )
    reference = ReferenceEvidence(
        reference_id="poisson-manufactured-analytic-v1",
        authority_id=authority.authority_id,
        kind=ReferenceKind.ANALYTIC,
        artifact_ref=worker_artifact,
        output_channels=("u",),
        coordinate_system="cartesian-unit-square",
        channel_units={"u": "1"},
        source_refs=(_source_ref(worker, "exact_solution"),),
        test_case_only=True,
        limitations=("Manufactured-reference qualification case only.",),
    )
    metric_contract = MetricContract(
        contract_id="poisson-user-confirmed-priority-v1",
        physical_model_authority_ref=worker_artifact,
        reference_evidence_refs=(worker_artifact,),
        metrics=(
            MetricRule(
                name="relative_l2",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="1",
            ),
            MetricRule(
                name="poisson_pde_residual_rms",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.PHYSICAL_MODEL,
                unit="1",
            ),
            MetricRule(
                name="poisson_boundary_max_abs",
                role=MetricRole.HARD_CONSTRAINT,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.PHYSICAL_MODEL,
                threshold=1.0e-6,
                unit="1",
            ),
            MetricRule(
                name="max_abs",
                role=MetricRole.DIAGNOSTIC,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="1",
            ),
            MetricRule(
                name="poisson_relative_h1",
                role=MetricRole.DIAGNOSTIC,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="1",
            ),
        ),
        primary_order=("relative_l2", "poisson_pde_residual_rms"),
        aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
        acceptable_regression_notes=(
            "The exact boundary constraint is mandatory; diagnostics cannot override primaries.",
        ),
    )
    return unit_system, authority, reference, metric_contract


def _physical_audit(worker: Path, unit_system: UnitSystemContract):
    parameter_specs = (
        ("domain-x-length", "Lx", "x coordinate span", "coordinate", 1.0),
        ("domain-y-length", "Ly", "y coordinate span", "coordinate", 1.0),
        ("solution-scale", "u_scale", "manufactured solution scale", "solution", 1.0),
        ("forcing-scale", "f_scale", "analytic forcing coefficient", "forcing", 2.0 * np.pi**2),
    )
    parameters = tuple(
        PhysicalParameterInput(
            parameter_id=parameter_id,
            symbol=symbol,
            meaning=meaning,
            quantity_kind=quantity_kind,
            raw_value=float(value),
            raw_unit="dimensionless",
            source_ref=_source_ref(worker, symbol),
        )
        for parameter_id, symbol, meaning, quantity_kind, value in parameter_specs
    )
    return PhysicalAuditService().audit(
        report_id="poisson-physical-audit-v1",
        unit_system=unit_system,
        parameters=parameters,
    )


def _manifest(
    *,
    worker: Path,
    training_python: Path,
    output_directory: Path,
    run_name: str,
    mode: str,
    sampler: str,
    seed: int,
    focus: tuple[float, float],
) -> RunManifest:
    command = (
        str(training_python),
        str(worker),
        "--mode",
        mode,
        "--sampler",
        sampler,
        "--seed",
        str(seed),
        "--focus-x",
        str(focus[0]),
        "--focus-y",
        str(focus[1]),
        "--focus-fraction",
        "0.125",
        "--focus-sigma",
        "0.10",
        "--output",
        str(output_directory),
    )
    return RunManifest(
        run_id=f"poisson-{run_name}-seed-{seed}",
        workflow_id=WORKFLOW_ID,
        experiment_id=f"poisson-{run_name}-seed-{seed}-experiment",
        idempotency_key=f"poisson-{run_name}-seed-{seed}",
        environment_name="pytorch2.3.1",
        interpreter=str(training_python),
        working_directory=str(worker.parent),
        command=command,
        config_ref=_artifact("poisson-worker-config", worker),
        output_root=str(output_directory),
        expected_artifacts=EXPECTED_OUTPUTS,
        checkpoint_policy="Persist model state, fields, metrics and hashes.",
        rollback_plan="Retain the uniform baseline when the candidate fails any gate.",
    )


def _run_stage(
    *,
    worker: Path,
    training_python: Path,
    root: Path,
    registry_path: Path,
    audit: AppendOnlyAuditStore,
    approval: ApprovalRecord,
    run_name: str,
    mode: str,
    sampler: str,
    seed: int,
    focus: tuple[float, float],
):
    output_directory = root / "outputs" / run_name
    manifest = _manifest(
        worker=worker,
        training_python=training_python,
        output_directory=output_directory,
        run_name=run_name,
        mode=mode,
        sampler=sampler,
        seed=seed,
        focus=focus,
    )
    backend_root = root / "backend" / run_name
    backend_root.mkdir(parents=True)
    collection_root = _collection_directory(root, run_name)
    runner = ManifestFirstRunner(
        SQLiteRunRegistry(registry_path), _build_local_backend(backend_root)
    )
    completed = _run_one(
        manifest=manifest,
        approval=approval,
        runner=runner,
        audit=audit,
        output_directory=output_directory,
        collection_directory=collection_root,
        expected_outputs=EXPECTED_OUTPUTS,
    )
    if completed.exit_code != 0:
        raise RuntimeError(f"Poisson stage failed: {run_name}")
    return manifest, completed, output_directory


def _collection_directory(root: Path, run_name: str) -> Path:
    destination = root / "collected" / run_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def _field(output: Path, artifact_ref: ArtifactRef) -> tuple[FieldData, FieldData]:
    payload = json.loads((output / "aligned_fields.json").read_text(encoding="utf-8"))
    x = np.asarray(payload["x"], dtype=float)
    y = np.asarray(payload["y"], dtype=float)
    prediction = np.asarray(payload["prediction"], dtype=float)
    reference = np.asarray(payload["reference"], dtype=float)
    residual = np.asarray(payload["pde_residual"], dtype=float)
    boundary_error = np.asarray(payload["boundary_error"], dtype=float)
    reference_identity = hashlib.sha256(reference.tobytes()).hexdigest()
    common = {
        "axes": ("x", "y"),
        "coordinates": {"x": x, "y": y},
        "reference_identity": reference_identity,
        "unit": "1",
        "coordinate_system": "cartesian-unit-square",
        "normalization": "physical",
    }
    return (
        FieldData(
            values=prediction,
            artifact_ref=artifact_ref,
            context_fields={
                "pde_residual": residual,
                "boundary_error": boundary_error,
            },
            **common,
        ),
        FieldData(values=reference, artifact_ref=artifact_ref, **common),
    )


def _metric_values(report) -> dict[str, float]:
    return {
        **{name: float(value) for name, value in report.global_metrics.items()},
        **{name: float(value) for name, value in report.domain_metrics.items()},
    }


def _semantic_strings(value: Any, *, key: str | None = None) -> tuple[str, ...]:
    if key in {"uri", "sha256"}:
        return ()
    if isinstance(value, dict):
        return tuple(
            text
            for child_key, child in value.items()
            for text in _semantic_strings(child, key=str(child_key))
        )
    if isinstance(value, list):
        return tuple(
            text for child in value for text in _semantic_strings(child)
        )
    return (value.casefold(),) if isinstance(value, str) else ()


def _replay(
    manifests: tuple[RunManifest, ...], approval: ApprovalRecord, registry_path: Path
) -> dict[str, Any]:
    checks = {}
    for manifest in manifests:
        backend = ForbiddenReplayBackend()
        submission = ManifestFirstRunner(
            SQLiteRunRegistry(registry_path), backend
        ).submit(manifest, approval)
        checks[manifest.run_id] = {
            "duplicate_submission": submission.duplicate,
            "backend_not_relaunched": backend.launch_count == 0,
        }
    return {
        "status": (
            "PASS"
            if all(all(item.values()) for item in checks.values())
            else "FAIL"
        ),
        "runs": checks,
    }


def execute(
    *,
    training_python: Path,
    output_root: Path,
    metric_approval_path: Path,
    execution_approval_path: Path,
    seed: int,
) -> None:
    training_python = training_python.absolute()
    if not training_python.is_file():
        raise ValueError("training Python must be an existing file")
    output_root = output_root.resolve(strict=False)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite Poisson evidence: {output_root}")
    worker = (Path(__file__).resolve().parent / "poisson_pinn_worker.py").resolve(
        strict=True
    )
    worker_hash_before = _sha256(worker)
    metric_approval = _approved_metric_record(metric_approval_path)
    execution_approval = _execution_approval(execution_approval_path)
    environment = _training_environment(training_python)
    output_root.mkdir(parents=True)

    evidence = output_root / "evidence"
    environment_ref = _write_json(evidence / "environment.json", environment)
    source_ref = _write_json(
        evidence / "source-snapshot.json",
        {"worker": str(worker), "sha256": worker_hash_before},
    )
    metric_approval_ref = _write_json(
        evidence / "metric-approval.json",
        metric_approval.model_dump(mode="json"),
    )
    execution_approval_ref = _write_json(
        evidence / "execution-approval.json",
        execution_approval.model_dump(mode="json"),
    )
    unit_system, authority, reference_evidence, metric_contract = _case_contracts(
        worker
    )
    physical = _physical_audit(worker, unit_system)
    basis = EvaluationBasisService().validate(
        authority=authority, references=(reference_evidence,)
    )
    if physical.status is not AuditStatus.PASS or not basis.ready:
        raise RuntimeError("Poisson audit or analytic evaluation basis failed")
    physical_ref = _write_json(
        evidence / "physical-audit.json", physical.model_dump(mode="json")
    )
    metric_contract_ref = _write_json(
        evidence / "metric-contract.json", metric_contract.model_dump(mode="json")
    )

    registry_path = output_root / "launch-registry.sqlite3"
    audit = AppendOnlyAuditStore(output_root / "audit.sqlite3")
    uniform_smoke = _run_stage(
        worker=worker,
        training_python=training_python,
        root=output_root,
        registry_path=registry_path,
        audit=audit,
        approval=execution_approval,
        run_name="uniform-smoke",
        mode="smoke",
        sampler="uniform",
        seed=seed,
        focus=(0.5, 0.5),
    )
    baseline = _run_stage(
        worker=worker,
        training_python=training_python,
        root=output_root,
        registry_path=registry_path,
        audit=audit,
        approval=execution_approval,
        run_name="uniform-full",
        mode="full",
        sampler="uniform",
        seed=seed,
        focus=(0.5, 0.5),
    )
    baseline_field, baseline_reference = _field(
        baseline[2], baseline[1].artifacts["aligned_fields.json"]
    )
    provider = PoissonMetricProvider()
    baseline_analysis = PredictionAnalyzer().analyze(
        report_id="poisson-baseline-diagnosis",
        prediction=baseline_field,
        reference=baseline_reference,
        top_k=10,
        domain_metric_providers=(provider,),
    )
    if baseline_analysis.status is not ResultStatus.VALID or baseline_analysis.max_abs is None:
        raise RuntimeError("Poisson baseline diagnosis is invalid")
    focus = (
        float(baseline_analysis.max_abs.coordinates["x"]),
        float(baseline_analysis.max_abs.coordinates["y"]),
    )
    diagnosis_ref = _write_json(
        evidence / "baseline-diagnosis.json",
        baseline_analysis.model_dump(mode="json"),
    )

    focused_smoke = _run_stage(
        worker=worker,
        training_python=training_python,
        root=output_root,
        registry_path=registry_path,
        audit=audit,
        approval=execution_approval,
        run_name="focused-smoke",
        mode="smoke",
        sampler="focused",
        seed=seed,
        focus=focus,
    )
    smoke_field, smoke_reference = _field(
        focused_smoke[2], focused_smoke[1].artifacts["aligned_fields.json"]
    )
    smoke_analysis = PredictionAnalyzer().analyze(
        report_id="poisson-focused-smoke",
        prediction=smoke_field,
        reference=smoke_reference,
        domain_metric_providers=(provider,),
    )
    smoke_valid = (
        uniform_smoke[1].exit_code == 0
        and focused_smoke[1].exit_code == 0
        and smoke_analysis.status is ResultStatus.VALID
    )
    if not smoke_valid:
        raise RuntimeError("Poisson smoke-first gate failed")

    candidate = _run_stage(
        worker=worker,
        training_python=training_python,
        root=output_root,
        registry_path=registry_path,
        audit=audit,
        approval=execution_approval,
        run_name="focused-full",
        mode="full",
        sampler="focused",
        seed=seed,
        focus=focus,
    )
    candidate_field, candidate_reference = _field(
        candidate[2], candidate[1].artifacts["aligned_fields.json"]
    )
    comparison = PredictionAnalyzer().compare(
        report_id="poisson-full-comparison",
        baseline=baseline_field,
        candidate=candidate_field,
        reference=candidate_reference,
        top_k=10,
        domain_metric_providers=(provider,),
    )
    comparison_ref = _write_json(
        evidence / "full-comparison.json", comparison.model_dump(mode="json")
    )
    baseline_values = _metric_values(comparison.baseline_report)
    candidate_values = _metric_values(comparison.candidate_report)
    decision = MetricDecisionService().compare(
        decision_id="poisson-focused-full-decision",
        contract=metric_contract,
        baseline=MetricValueSet(subject_id=baseline[0].run_id, values=baseline_values),
        candidate=MetricValueSet(subject_id=candidate[0].run_id, values=candidate_values),
        observed_failure_mechanism=(
            "localized analytic-reference error at the diagnosed baseline maximum"
        ),
    )
    decision_payload = decision.model_dump(mode="json")
    decision_payload.update(
        {
            "selected_intervention": (
                "12.5 percent localized collocation"
                if decision.status is DecisionStatus.ACCEPT
                else None
            ),
            "unchanged_controls": [
                "governing equation and analytic reference",
                "boundary ansatz and unit-square geometry",
                "network initialization and architecture",
                "optimizer, schedule, epoch budget and point count",
                "evaluation grid",
            ],
            "supporting_evidence_refs": [comparison_ref.model_dump(mode="json")],
            "falsification_condition": "Reject when any primary, hard constraint or provenance gate fails.",
            "rollback_plan": "Retain the uniform baseline and preserve candidate evidence.",
        }
    )
    decision = DecisionRecord.model_validate(decision_payload)
    evaluation = ModelEvaluationReport(
        report_id="poisson-focused-full-evaluation",
        status=comparison.status,
        physical_model_authority_ref=_artifact("poisson-worker-authority", worker),
        metric_values=candidate_values,
        metric_bases={
            name: (
                MetricEvidenceBasis.PHYSICAL_MODEL
                if name.startswith("poisson_pde") or name.startswith("poisson_boundary")
                else MetricEvidenceBasis.REFERENCE_EVIDENCE
            )
            for name in candidate_values
        },
        prediction_analysis_ref=comparison_ref,
        diagnostic_refs=(candidate[1].artifacts["aligned_fields.json"], diagnosis_ref),
        domain_provider_ids=(provider.provider_id,),
        checks={
            "physical_audit": physical.status is AuditStatus.PASS,
            "analytic_basis": basis.ready,
            "aligned_comparison": comparison.status is ResultStatus.VALID,
            "smoke_first": smoke_valid,
            "worker_unchanged": worker_hash_before == _sha256(worker),
        },
    )
    manifest_ref = _write_json(
        evidence / "candidate-run-manifest.json",
        candidate[0].model_dump(mode="json"),
    )
    validation = RunValidationService().validate(
        report_id="poisson-focused-full-validation",
        validation_input=RunValidationInput(
            run_id=candidate[0].run_id,
            process_exit_code=candidate[1].exit_code,
            physical_audit=physical,
            model_evaluation=evaluation,
            metric_decision=decision,
            required_artifacts=EXPECTED_OUTPUTS,
            produced_artifacts=candidate[1].artifacts,
            run_manifest_ref=manifest_ref,
            source_snapshot_ref=source_ref,
            dataset_refs=(candidate[1].artifacts["aligned_fields.json"],),
            environment_ref=environment_ref,
            random_seed=seed,
        ),
    )
    validation_ref = _write_json(
        evidence / "validation.json", validation.model_dump(mode="json")
    )
    integrity_checks = {
        key: value for key, value in validation.checks.items() if key != "metric_decision"
    }
    manifests = (
        uniform_smoke[0],
        baseline[0],
        focused_smoke[0],
        candidate[0],
    )
    replay = _replay(manifests, execution_approval, registry_path)
    provenance_refs = (
        environment_ref,
        source_ref,
        metric_approval_ref,
        execution_approval_ref,
        physical_ref,
        metric_contract_ref,
        diagnosis_ref,
        comparison_ref,
        manifest_ref,
        validation_ref,
        *candidate[1].artifacts.values(),
    )
    provenance_valid = all(
        _verify_artifact_reference(item.model_dump(mode="json"))
        for item in provenance_refs
    )
    report = {
        "workflow_id": WORKFLOW_ID,
        "case_id": "poisson-manufactured-unit-square-v1",
        "seed": seed,
        "environment": environment,
        "audit": {
            "physical_status": physical.status.value,
            "evaluation_basis_ready": basis.ready,
            "metric_approval_ref": metric_approval_ref.model_dump(mode="json"),
            "execution_approval_ref": execution_approval_ref.model_dump(mode="json"),
        },
        "sequence": [
            "audit_and_metric_confirmation",
            "uniform_smoke",
            "uniform_full_baseline",
            "localized_baseline_diagnosis",
            "focused_smoke",
            "focused_full",
            "full_comparison",
            "replay_and_provenance",
        ],
        "intervention": {
            "target": "collocation_sampler",
            "uniform_fraction_before": 1.0,
            "localized_fraction_after": 0.125,
            "focus": {"x": focus[0], "y": focus[1]},
            "sigma": 0.10,
        },
        "smoke": {
            "status": "PASS",
            "scientific_effectiveness_claimed": False,
            "analysis_status": smoke_analysis.status.value,
        },
        "baseline": baseline_analysis.model_dump(mode="json"),
        "comparison": comparison.model_dump(mode="json"),
        "decision": decision.model_dump(mode="json"),
        "validation": validation.model_dump(mode="json"),
        "evidence_integrity": {
            "status": "PASS" if all(integrity_checks.values()) else "FAIL",
            "checks": integrity_checks,
        },
        "replay": replay,
        "provenance": {
            "status": "PASS" if provenance_valid else "FAIL",
            "worker_unchanged": worker_hash_before == _sha256(worker),
            "evidence_ref_count": len(provenance_refs),
        },
    }
    report_ref = _write_json(output_root / "poisson-execution-report.json", report)
    scan_paths = (
        evidence / "metric-contract.json",
        candidate[2] / "case_contract.json",
        output_root / "poisson-execution-report.json",
    )
    violations = {}
    for path in scan_paths:
        semantic_text = "\n".join(
            _semantic_strings(json.loads(path.read_text(encoding="utf-8")))
        )
        terms = tuple(token for token in SEMANTIC_SCAN_TOKENS if token in semantic_text)
        if terms:
            violations[str(path)] = terms
    semantic_audit = {
        "policy_id": "poisson-contract-isolation-v1",
        "status": "PASS" if not violations else "FAIL",
        "scanned_sha256": {str(path): _sha256(path) for path in scan_paths},
        "violation_count": sum(len(terms) for terms in violations.values()),
        "report_ref": report_ref.model_dump(mode="json"),
    }
    _write_json(output_root / "poisson-semantic-isolation-audit.json", semantic_audit)
    required = (
        physical.status is AuditStatus.PASS,
        basis.ready,
        smoke_valid,
        comparison.status is ResultStatus.VALID,
        all(integrity_checks.values()),
        replay["status"] == "PASS",
        provenance_valid,
        not violations,
    )
    if not all(required):
        raise RuntimeError(
            "Poisson qualification completed with a failed gate; evidence retained"
        )
    print(
        json.dumps(
            {
                "report": str(output_root / "poisson-execution-report.json"),
                "decision": decision.status.value,
                "validation": validation.status.value,
                "replay": replay["status"],
                "semantic_isolation": semantic_audit["status"],
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-python", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--metric-approval", type=Path, required=True)
    parser.add_argument("--execution-approval", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    execute(
        training_python=args.training_python,
        output_root=args.output_root,
        metric_approval_path=args.metric_approval,
        execution_approval_path=args.execution_approval,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()

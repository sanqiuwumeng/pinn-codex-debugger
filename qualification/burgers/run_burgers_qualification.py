"""Governed multi-seed qualification for the classic viscous Burgers PINN."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
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
    ExperimentGovernanceService,
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
    BudgetSpec,
    DecisionRecord,
    DecisionStatus,
    ExperimentDraft,
    InterventionChange,
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
from pinn_strategy_system.domain_metrics.burgers import (  # noqa: E402
    BurgersMetricProvider,
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

WORKFLOW_ID = "burgers-cross-domain-qualification-v1"
APPROVAL_SCOPE = f"qualification:{WORKFLOW_ID}"
FROZEN_SEEDS = (7, 42, 2026)
EXPECTED_OUTPUTS = (
    "case_contract.json",
    "run_config.json",
    "runtime_environment.json",
    "training_history.json",
    "field_metrics.json",
    "aligned_fields.npz",
    "model.pt",
    "reproducibility_manifest.json",
)
SEMANTIC_SCAN_TOKENS = (
    "temperature",
    "kelvin",
    "phase-change",
    "melt-region",
    "heat-transfer",
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
        "import json,sys,torch,numpy;"
        "print(json.dumps({'python':sys.version.split()[0],"
        "'executable':sys.executable,'torch':torch.__version__,"
        "'numpy':numpy.__version__,'cuda_available':torch.cuda.is_available()},"
        "sort_keys=True))"
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
            "Burgers qualification requires Python 3.11.11, torch 2.3.1 and NumPy 2.2.5"
        )
    return environment


def _metric_approval(path: Path) -> ApprovalRecord:
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


def _source_ref(path: Path, symbol: str) -> SourceRef:
    return SourceRef(uri=path.as_uri(), sha256=_sha256(path), symbol=symbol)


def _reference_gate(reference_root: Path) -> dict[str, Any]:
    convergence_path = reference_root / "reference_convergence.json"
    manifest_path = reference_root / "reference_manifest.json"
    fields_path = reference_root / "reference_fields.npz"
    convergence = json.loads(convergence_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest["artifacts"]["reference_fields.npz"]["sha256"]
    checks = {
        "convergence_status": convergence["status"] == "PASS",
        "all_convergence_checks": all(convergence["checks"].values()),
        "field_hash": _sha256(fields_path) == expected,
        "successive_difference_reduces": (
            convergence["medium_to_fine_relative_l2"]
            < convergence["coarse_to_medium_relative_l2"]
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "convergence": convergence,
        "fields": fields_path,
        "convergence_path": convergence_path,
        "manifest_path": manifest_path,
    }


def _contracts(
    *, worker: Path, reference_fields: Path
) -> tuple[UnitSystemContract, PhysicalModelAuthority, ReferenceEvidence, MetricContract]:
    worker_ref = _artifact("burgers-worker-source", worker)
    reference_ref = _artifact("burgers-converged-reference", reference_fields)
    unit_system = UnitSystemContract(
        unit_system_id="burgers-dimensionless-v1",
        name="dimensionless Burgers benchmark coordinates and solution",
        quantity_units={
            "space_coordinate": "dimensionless",
            "time_coordinate": "dimensionless",
            "solution": "dimensionless",
            "u": "dimensionless",
            "viscosity": "dimensionless",
        },
        source_refs=(_source_ref(worker, "case_contract"),),
        confirmed_by_user=True,
    )
    authority = PhysicalModelAuthority(
        authority_id="viscous-burgers-standard-authority-v1",
        project_id="universal-pinn-cross-domain-qualification",
        model_family="pinn",
        pde_family="viscous-burgers",
        task_type="forward",
        governing_equation_refs=(_source_ref(worker, "pde_residual"),),
        boundary_condition_refs=(_source_ref(worker, "BurgersNet.forward"),),
        initial_condition_refs=(_source_ref(worker, "BurgersNet.forward"),),
        geometry_refs=(_source_ref(worker, "case_contract"),),
        parameter_source_refs=(_source_ref(worker, "VISCOSITY"),),
        output_channels=("u",),
        unit_system=unit_system,
        confirmed_by_user=True,
    )
    reference = ReferenceEvidence(
        reference_id="viscous-burgers-converged-numerical-v1",
        authority_id=authority.authority_id,
        kind=ReferenceKind.NUMERICAL,
        artifact_ref=reference_ref,
        output_channels=("u",),
        coordinate_system="dimensionless-time-space",
        channel_units={"u": "1"},
        source_refs=(_source_ref(worker.parent / "burgers_reference.py", "solve"),),
        test_case_only=True,
        limitations=(
            "Independent converged numerical reference for this benchmark only.",
        ),
    )
    metrics = MetricContract(
        contract_id="burgers-user-confirmed-metric-policy-v1",
        physical_model_authority_ref=worker_ref,
        reference_evidence_refs=(reference_ref,),
        metrics=(
            MetricRule(
                name="relative_l2",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="1",
            ),
            MetricRule(
                name="max_abs",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="1",
            ),
            MetricRule(
                name="burgers_initial_max_abs",
                role=MetricRole.HARD_CONSTRAINT,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.PHYSICAL_MODEL,
                threshold=1.0e-6,
                unit="1",
            ),
            MetricRule(
                name="burgers_boundary_max_abs",
                role=MetricRole.HARD_CONSTRAINT,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.PHYSICAL_MODEL,
                threshold=1.0e-6,
                unit="1",
            ),
            MetricRule(
                name="burgers_pde_residual_rms",
                role=MetricRole.GUARDRAIL,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.PHYSICAL_MODEL,
                max_relative_regression=0.25,
                unit="1",
            ),
            MetricRule(
                name="burgers_high_gradient_rmse",
                role=MetricRole.GUARDRAIL,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                max_relative_regression=0.10,
                unit="1",
            ),
            MetricRule(
                name="burgers_high_gradient_max_abs",
                role=MetricRole.DIAGNOSTIC,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="1",
            ),
        ),
        primary_order=("relative_l2", "max_abs"),
        aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
        acceptable_regression_notes=(
            "PDE residual may regress by at most 25 percent.",
            "High-gradient RMSE may regress by at most 10 percent.",
            "Initial and boundary maximum errors must remain at or below 1e-6.",
        ),
    )
    return unit_system, authority, reference, metrics


def _physical_audit(worker: Path, unit_system: UnitSystemContract):
    parameters = tuple(
        PhysicalParameterInput(
            parameter_id=parameter_id,
            symbol=symbol,
            meaning=meaning,
            quantity_kind=quantity_kind,
            raw_value=value,
            raw_unit="dimensionless",
            source_ref=_source_ref(worker, symbol),
        )
        for parameter_id, symbol, meaning, quantity_kind, value in (
            ("x-lower", "x_min", "lower space coordinate", "space_coordinate", -1.0),
            ("x-upper", "x_max", "upper space coordinate", "space_coordinate", 1.0),
            ("t-upper", "t_max", "upper time coordinate", "time_coordinate", 1.0),
            ("solution-scale", "u_scale", "initial solution scale", "solution", 1.0),
            ("viscosity", "VISCOSITY", "viscous coefficient", "viscosity", 0.01 / np.pi),
        )
    )
    return PhysicalAuditService().audit(
        report_id="burgers-physical-audit-v1",
        unit_system=unit_system,
        parameters=parameters,
    )


def _manifest(
    *,
    worker: Path,
    training_python: Path,
    reference_fields: Path,
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
        "--focus-t",
        str(focus[1]),
        "--focus-fraction",
        "0.125",
        "--sigma-x",
        "0.15",
        "--sigma-t",
        "0.10",
        "--reference",
        str(reference_fields),
        "--output",
        str(output_directory),
    )
    return RunManifest(
        run_id=f"burgers-{run_name}",
        workflow_id=WORKFLOW_ID,
        experiment_id=f"burgers-{run_name}-experiment",
        idempotency_key=f"burgers-{run_name}-seed-{seed}",
        environment_name="pytorch2.3.1",
        interpreter=str(training_python),
        working_directory=str(worker.parent),
        command=command,
        config_ref=_artifact("burgers-worker-config", worker),
        output_root=str(output_directory),
        expected_artifacts=EXPECTED_OUTPUTS,
        checkpoint_policy="Persist model, aligned fields, metrics and hashes.",
        rollback_plan="Retain the paired uniform baseline and rejected evidence.",
    )


def _run_stage(
    *,
    worker: Path,
    training_python: Path,
    reference_fields: Path,
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
        reference_fields=reference_fields,
        output_directory=output_directory,
        run_name=run_name,
        mode=mode,
        sampler=sampler,
        seed=seed,
        focus=focus,
    )
    backend_root = root / "backend" / run_name
    backend_root.mkdir(parents=True)
    completed = _run_one(
        manifest=manifest,
        approval=approval,
        runner=ManifestFirstRunner(
            SQLiteRunRegistry(registry_path), _build_local_backend(backend_root)
        ),
        audit=audit,
        output_directory=output_directory,
        collection_directory=root / "collected" / run_name,
        expected_outputs=EXPECTED_OUTPUTS,
    )
    if completed.exit_code != 0:
        raise RuntimeError(f"Burgers stage failed: {run_name}")
    return manifest, completed, output_directory


def _field(output: Path, artifact_ref: ArtifactRef) -> tuple[FieldData, FieldData]:
    with np.load(output / "aligned_fields.npz", allow_pickle=False) as payload:
        x = np.asarray(payload["x"], dtype=float)
        time = np.asarray(payload["t"], dtype=float)
        prediction = np.asarray(payload["prediction"], dtype=float)
        reference = np.asarray(payload["reference"], dtype=float)
        residual = np.asarray(payload["pde_residual"], dtype=float)
    reference_identity = hashlib.sha256(reference.tobytes()).hexdigest()
    common = {
        "axes": ("t", "x"),
        "coordinates": {"t": time, "x": x},
        "reference_identity": reference_identity,
        "unit": "1",
        "coordinate_system": "dimensionless-time-space",
        "normalization": "physical",
    }
    return (
        FieldData(
            values=prediction,
            artifact_ref=artifact_ref,
            context_fields={"pde_residual": residual},
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
    runs = {}
    for manifest in manifests:
        backend = ForbiddenReplayBackend()
        submission = ManifestFirstRunner(
            SQLiteRunRegistry(registry_path), backend
        ).submit(manifest, approval)
        runs[manifest.run_id] = {
            "duplicate_submission": submission.duplicate,
            "backend_not_relaunched": backend.launch_count == 0,
        }
    return {
        "status": (
            "PASS" if all(all(check.values()) for check in runs.values()) else "FAIL"
        ),
        "runs": runs,
    }


def _governed_experiment(
    *,
    seed: int,
    focus: tuple[float, float],
    baseline_ref: ArtifactRef,
    diagnosis_ref: ArtifactRef,
    source_ref: ArtifactRef,
    reference_ref: ArtifactRef,
    environment_ref: ArtifactRef,
    metric_contract_ref: ArtifactRef,
    output_root: Path,
    worker: Path,
):
    draft = ExperimentDraft(
        experiment_id=f"burgers-focused-seed-{seed}",
        project_id="universal-pinn-cross-domain-qualification",
        observed_failure_mechanism=(
            f"localized baseline error near x={focus[0]} and t={focus[1]} in the "
            "reference high-gradient region"
        ),
        supporting_evidence_refs=(diagnosis_ref,),
        interventions=(
            InterventionChange(
                target="fixed_collocation_sampler",
                before={"uniform_fraction": 1.0, "focused_fraction": 0.0},
                after={"uniform_fraction": 0.875, "focused_fraction": 0.125},
                rationale="Test one localized sampling change at the diagnosed error peak.",
                source_ref=_source_ref(worker, "sample_points"),
            ),
        ),
        unchanged_controls=(
            "equation, initial condition and boundary condition",
            "converged numerical reference and evaluation grid",
            "network initialization and architecture",
            "optimizer, schedule, epoch budget and total collocation count",
            f"random seed {seed} within the paired comparison",
        ),
        expected_primary_metric_movement={
            "relative_l2": "decrease",
            "max_abs": "decrease when relative_l2 is tied",
        },
        guardrail_limits={
            "initial_max_abs": 1.0e-6,
            "boundary_max_abs": 1.0e-6,
            "pde_residual_relative_regression": 0.25,
            "high_gradient_rmse_relative_regression": 0.10,
        },
        smoke_budget=BudgetSpec(max_steps=30, resource_description="bounded CPU smoke"),
        full_budget=BudgetSpec(max_steps=2500, max_seconds=1800, resource_description="paired local CPU full run"),
        falsification_condition=(
            "Reject this seed when a primary, hard constraint, guardrail or provenance gate fails."
        ),
        rollback_plan="Retain the paired uniform baseline and preserve rejected evidence.",
        source_snapshot_ref=source_ref,
        dataset_refs=(reference_ref,),
        environment_ref=environment_ref,
        random_seed=seed,
        baseline_run_ref=baseline_ref,
        metric_contract_ref=metric_contract_ref,
        output_root=str(output_root),
        checkpoint_policy="Persist all run and model artifacts before comparison.",
        expected_artifacts=EXPECTED_OUTPUTS,
    )
    completeness = ExperimentGovernanceService().audit(
        report_id=f"burgers-seed-{seed}-experiment-completeness",
        draft=draft,
    )
    if completeness.status is not AuditStatus.PASS:
        raise RuntimeError(f"Burgers experiment completeness failed: {completeness}")
    return completeness


def execute(
    *,
    training_python: Path,
    reference_root: Path,
    output_root: Path,
    metric_approval_path: Path,
    execution_approval_path: Path,
) -> None:
    training_python = training_python.resolve(strict=True)
    reference_root = reference_root.resolve(strict=True)
    output_root = output_root.resolve(strict=False)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite Burgers evidence: {output_root}")
    worker = (Path(__file__).resolve().parent / "burgers_pinn_worker.py").resolve(
        strict=True
    )
    reference_solver = (
        Path(__file__).resolve().parent / "burgers_reference.py"
    ).resolve(strict=True)
    reference_gate = _reference_gate(reference_root)
    if reference_gate["status"] != "PASS":
        raise RuntimeError("Burgers numerical reference is not decision-ready")
    environment = _training_environment(training_python)
    metric_approval = _metric_approval(metric_approval_path)
    approval = _execution_approval(execution_approval_path)
    output_root.mkdir(parents=True)
    (output_root / "collected").mkdir()

    evidence = output_root / "evidence"
    source_ref = _write_json(
        evidence / "source-snapshot.json",
        {
            "worker": {"path": str(worker), "sha256": _sha256(worker)},
            "reference_solver": {
                "path": str(reference_solver),
                "sha256": _sha256(reference_solver),
            },
        },
    )
    environment_ref = _write_json(evidence / "environment.json", environment)
    metric_approval_ref = _write_json(
        evidence / "metric-approval.json",
        metric_approval.model_dump(mode="json"),
    )
    execution_approval_ref = _write_json(
        evidence / "execution-approval.json",
        approval.model_dump(mode="json"),
    )
    reference_fields = reference_gate["fields"]
    reference_ref = _artifact("burgers-converged-reference", reference_fields)
    reference_gate_ref = _write_json(
        evidence / "reference-gate.json",
        {
            key: value
            for key, value in reference_gate.items()
            if key not in {"fields", "convergence_path", "manifest_path"}
        },
    )
    unit_system, authority, reference_evidence, metric_contract = _contracts(
        worker=worker, reference_fields=reference_fields
    )
    physical = _physical_audit(worker, unit_system)
    basis = EvaluationBasisService().validate(
        authority=authority, references=(reference_evidence,)
    )
    if physical.status is not AuditStatus.PASS or not basis.ready:
        raise RuntimeError("Burgers physical audit or evaluation basis failed")
    physical_ref = _write_json(
        evidence / "physical-audit.json", physical.model_dump(mode="json")
    )
    metric_contract_ref = _write_json(
        evidence / "metric-contract.json", metric_contract.model_dump(mode="json")
    )

    registry_path = output_root / "launch-registry.sqlite3"
    audit = AppendOnlyAuditStore(output_root / "audit.sqlite3")
    manifests: list[RunManifest] = []
    seed_reports = []
    provider = BurgersMetricProvider()

    uniform_smoke = _run_stage(
        worker=worker,
        training_python=training_python,
        reference_fields=reference_fields,
        root=output_root,
        registry_path=registry_path,
        audit=audit,
        approval=approval,
        run_name="uniform-smoke-seed-7",
        mode="smoke",
        sampler="uniform",
        seed=7,
        focus=(0.0, 0.75),
    )
    manifests.append(uniform_smoke[0])
    smoke_field, smoke_reference = _field(
        uniform_smoke[2], uniform_smoke[1].artifacts["aligned_fields.npz"]
    )
    uniform_smoke_analysis = PredictionAnalyzer().analyze(
        report_id="burgers-uniform-smoke",
        prediction=smoke_field,
        reference=smoke_reference,
        domain_metric_providers=(provider,),
    )
    if uniform_smoke_analysis.status is not ResultStatus.VALID:
        raise RuntimeError("Burgers uniform smoke analysis failed")

    focused_smoke_completed = False
    for seed in FROZEN_SEEDS:
        baseline = _run_stage(
            worker=worker,
            training_python=training_python,
            reference_fields=reference_fields,
            root=output_root,
            registry_path=registry_path,
            audit=audit,
            approval=approval,
            run_name=f"uniform-full-seed-{seed}",
            mode="full",
            sampler="uniform",
            seed=seed,
            focus=(0.0, 0.75),
        )
        manifests.append(baseline[0])
        baseline_field, baseline_reference = _field(
            baseline[2], baseline[1].artifacts["aligned_fields.npz"]
        )
        baseline_analysis = PredictionAnalyzer().analyze(
            report_id=f"burgers-baseline-seed-{seed}",
            prediction=baseline_field,
            reference=baseline_reference,
            top_k=10,
            domain_metric_providers=(provider,),
        )
        if baseline_analysis.status is not ResultStatus.VALID or baseline_analysis.max_abs is None:
            raise RuntimeError(f"Burgers baseline diagnosis failed for seed {seed}")
        focus = (
            float(baseline_analysis.max_abs.coordinates["x"]),
            float(baseline_analysis.max_abs.coordinates["t"]),
        )
        diagnosis_ref = _write_json(
            evidence / f"baseline-diagnosis-seed-{seed}.json",
            baseline_analysis.model_dump(mode="json"),
        )
        if not focused_smoke_completed:
            focused_smoke = _run_stage(
                worker=worker,
                training_python=training_python,
                reference_fields=reference_fields,
                root=output_root,
                registry_path=registry_path,
                audit=audit,
                approval=approval,
                run_name="focused-smoke-seed-7",
                mode="smoke",
                sampler="focused",
                seed=7,
                focus=focus,
            )
            manifests.append(focused_smoke[0])
            focused_field, focused_reference = _field(
                focused_smoke[2], focused_smoke[1].artifacts["aligned_fields.npz"]
            )
            focused_smoke_analysis = PredictionAnalyzer().analyze(
                report_id="burgers-focused-smoke",
                prediction=focused_field,
                reference=focused_reference,
                domain_metric_providers=(provider,),
            )
            if focused_smoke_analysis.status is not ResultStatus.VALID:
                raise RuntimeError("Burgers focused smoke analysis failed")
            focused_smoke_completed = True

        completeness = _governed_experiment(
            seed=seed,
            focus=focus,
            baseline_ref=baseline[1].artifacts["aligned_fields.npz"],
            diagnosis_ref=diagnosis_ref,
            source_ref=source_ref,
            reference_ref=reference_ref,
            environment_ref=environment_ref,
            metric_contract_ref=metric_contract_ref,
            output_root=output_root,
            worker=worker,
        )
        experiment_ref = _write_json(
            evidence / f"experiment-spec-seed-{seed}.json",
            completeness.experiment_spec.model_dump(mode="json"),
        )
        candidate = _run_stage(
            worker=worker,
            training_python=training_python,
            reference_fields=reference_fields,
            root=output_root,
            registry_path=registry_path,
            audit=audit,
            approval=approval,
            run_name=f"focused-full-seed-{seed}",
            mode="full",
            sampler="focused",
            seed=seed,
            focus=focus,
        )
        manifests.append(candidate[0])
        candidate_field, candidate_reference = _field(
            candidate[2], candidate[1].artifacts["aligned_fields.npz"]
        )
        comparison = PredictionAnalyzer().compare(
            report_id=f"burgers-comparison-seed-{seed}",
            baseline=baseline_field,
            candidate=candidate_field,
            reference=candidate_reference,
            top_k=10,
            domain_metric_providers=(provider,),
        )
        comparison_ref = _write_json(
            evidence / f"comparison-seed-{seed}.json",
            comparison.model_dump(mode="json"),
        )
        baseline_values = _metric_values(comparison.baseline_report)
        candidate_values = _metric_values(comparison.candidate_report)
        decision = MetricDecisionService().compare(
            decision_id=f"burgers-decision-seed-{seed}",
            contract=metric_contract,
            baseline=MetricValueSet(
                subject_id=baseline[0].run_id, values=baseline_values
            ),
            candidate=MetricValueSet(
                subject_id=candidate[0].run_id, values=candidate_values
            ),
            observed_failure_mechanism=(
                "localized reference error in the diagnosed high-gradient region"
            ),
        )
        decision_payload = decision.model_dump(mode="json")
        decision_payload.update(
            {
                "selected_intervention": (
                    "12.5 percent localized fixed collocation"
                    if decision.status is DecisionStatus.ACCEPT
                    else None
                ),
                "unchanged_controls": list(
                    completeness.experiment_spec.unchanged_controls
                ),
                "supporting_evidence_refs": [
                    comparison_ref.model_dump(mode="json")
                ],
                "expected_primary_metric_movement": dict(
                    completeness.experiment_spec.expected_primary_metric_movement
                ),
                "guardrail_limits": dict(
                    completeness.experiment_spec.guardrail_limits
                ),
                "falsification_condition": completeness.experiment_spec.falsification_condition,
                "rollback_plan": completeness.experiment_spec.rollback_plan,
            }
        )
        decision = DecisionRecord.model_validate(decision_payload)
        evaluation = ModelEvaluationReport(
            report_id=f"burgers-evaluation-seed-{seed}",
            status=comparison.status,
            physical_model_authority_ref=_artifact(
                "burgers-worker-authority", worker
            ),
            metric_values=candidate_values,
            metric_bases={
                name: (
                    MetricEvidenceBasis.PHYSICAL_MODEL
                    if name.startswith("burgers_pde")
                    or name.startswith("burgers_initial")
                    or name.startswith("burgers_boundary")
                    else MetricEvidenceBasis.REFERENCE_EVIDENCE
                )
                for name in candidate_values
            },
            prediction_analysis_ref=comparison_ref,
            diagnostic_refs=(
                candidate[1].artifacts["aligned_fields.npz"],
                diagnosis_ref,
                reference_gate_ref,
            ),
            domain_provider_ids=(provider.provider_id,),
            checks={
                "physical_audit": physical.status is AuditStatus.PASS,
                "reference_gate": reference_gate["status"] == "PASS",
                "evaluation_basis": basis.ready,
                "aligned_comparison": comparison.status is ResultStatus.VALID,
                "smoke_first": focused_smoke_completed,
                "single_intervention": completeness.status is AuditStatus.PASS,
                "source_unchanged": (
                    _sha256(worker) == json.loads(
                        (evidence / "source-snapshot.json").read_text(encoding="utf-8")
                    )["worker"]["sha256"]
                ),
            },
        )
        manifest_ref = _write_json(
            evidence / f"candidate-manifest-seed-{seed}.json",
            candidate[0].model_dump(mode="json"),
        )
        validation = RunValidationService().validate(
            report_id=f"burgers-validation-seed-{seed}",
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
                dataset_refs=(reference_ref,),
                environment_ref=environment_ref,
                random_seed=seed,
            ),
        )
        validation_ref = _write_json(
            evidence / f"validation-seed-{seed}.json",
            validation.model_dump(mode="json"),
        )
        integrity_checks = {
            key: value
            for key, value in validation.checks.items()
            if key != "metric_decision"
        }
        seed_reports.append(
            {
                "seed": seed,
                "focus": {"x": focus[0], "t": focus[1]},
                "experiment_spec_ref": experiment_ref.model_dump(mode="json"),
                "baseline": comparison.baseline_report.model_dump(mode="json"),
                "candidate": comparison.candidate_report.model_dump(mode="json"),
                "metric_deltas": dict(comparison.metric_deltas),
                "error_migrated": comparison.error_migrated,
                "decision": decision.model_dump(mode="json"),
                "validation": validation.model_dump(mode="json"),
                "validation_ref": validation_ref.model_dump(mode="json"),
                "evidence_integrity": {
                    "status": (
                        "PASS" if all(integrity_checks.values()) else "FAIL"
                    ),
                    "checks": integrity_checks,
                },
                "process": {
                    "baseline": {
                        "submission": baseline[1].submission,
                        "monitoring": baseline[1].monitoring,
                    },
                    "candidate": {
                        "submission": candidate[1].submission,
                        "monitoring": candidate[1].monitoring,
                    },
                },
            }
        )

    replay = _replay(tuple(manifests), approval, registry_path)
    candidate_metric_names = (
        "relative_l2",
        "max_abs",
        "burgers_pde_residual_rms",
        "burgers_high_gradient_rmse",
    )
    uncertainty = {}
    for metric in candidate_metric_names:
        values = [float(item["candidate"]["global_metrics"].get(metric, item["candidate"]["domain_metrics"].get(metric))) for item in seed_reports]
        uncertainty[metric] = {
            "mean": statistics.fmean(values),
            "sample_std": statistics.stdev(values),
            "min": min(values),
            "max": max(values),
        }
    report = {
        "workflow_id": WORKFLOW_ID,
        "case_id": "viscous-burgers-standard-v1",
        "frozen_seeds": list(FROZEN_SEEDS),
        "predeclared_seed_policy": "No result-based omission or rerun.",
        "environment": environment,
        "audit": {
            "physical": physical.model_dump(mode="json"),
            "evaluation_basis_ready": basis.ready,
            "reference_gate": {
                "status": reference_gate["status"],
                "checks": reference_gate["checks"],
                "convergence": reference_gate["convergence"],
            },
            "metric_contract": metric_contract.model_dump(mode="json"),
        },
        "intervention": {
            "target": "fixed_collocation_sampler",
            "uniform_fraction_before": 1.0,
            "localized_fraction_after": 0.125,
            "focus_rule": "paired baseline maximum-error coordinate",
            "sigma_x": 0.15,
            "sigma_t": 0.10,
        },
        "smoke": {
            "uniform_status": uniform_smoke_analysis.status.value,
            "focused_status": "RESULT_VALID" if focused_smoke_completed else "RESULT_INVALID",
            "scientific_effectiveness_claimed": False,
        },
        "per_seed": seed_reports,
        "candidate_uncertainty": uncertainty,
        "accepted_seeds": [
            item["seed"]
            for item in seed_reports
            if item["decision"]["status"] == "ACCEPT"
        ],
        "rejected_seeds": [
            item["seed"]
            for item in seed_reports
            if item["decision"]["status"] != "ACCEPT"
        ],
        "replay": replay,
    }
    report_path = output_root / "burgers-qualification-report.json"
    report_ref = _write_json(report_path, report)
    scan_paths = (
        evidence / "metric-contract.json",
        report_path,
        *(output_root / "outputs" / f"focused-full-seed-{seed}" / "case_contract.json" for seed in FROZEN_SEEDS),
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
        "policy_id": "burgers-contract-isolation-v1",
        "status": "PASS" if not violations else "FAIL",
        "scanned_sha256": {str(path): _sha256(path) for path in scan_paths},
        "violation_count": sum(len(terms) for terms in violations.values()),
        "report_ref": report_ref.model_dump(mode="json"),
    }
    _write_json(output_root / "burgers-semantic-isolation-audit.json", semantic_audit)
    provenance_refs = (
        source_ref,
        environment_ref,
        reference_ref,
        reference_gate_ref,
        physical_ref,
        metric_contract_ref,
        metric_approval_ref,
        execution_approval_ref,
        *(
            ArtifactRef.model_validate(item["validation_ref"])
            for item in seed_reports
        ),
    )
    provenance_valid = all(
        _verify_artifact_reference(item.model_dump(mode="json"))
        for item in provenance_refs
    )
    qualification_checks = {
        "reference": reference_gate["status"] == "PASS",
        "physical_audit": physical.status is AuditStatus.PASS,
        "evaluation_basis": basis.ready,
        "three_predeclared_seeds": len(seed_reports) == len(FROZEN_SEEDS),
        "all_seed_evidence_integrity": all(
            item["evidence_integrity"]["status"] == "PASS"
            for item in seed_reports
        ),
        "replay": replay["status"] == "PASS",
        "provenance": provenance_valid,
        "semantic_isolation": semantic_audit["status"] == "PASS",
        "worker_unchanged": _sha256(worker)
        == json.loads((evidence / "source-snapshot.json").read_text(encoding="utf-8"))["worker"]["sha256"],
        "reference_solver_unchanged": _sha256(reference_solver)
        == json.loads((evidence / "source-snapshot.json").read_text(encoding="utf-8"))["reference_solver"]["sha256"],
    }
    final = {
        "status": (
            "PASS_WITH_REJECTIONS"
            if all(qualification_checks.values()) and report["rejected_seeds"]
            else "PASS"
            if all(qualification_checks.values())
            else "FAIL"
        ),
        "checks": qualification_checks,
        "report_ref": report_ref.model_dump(mode="json"),
        "semantic_audit": semantic_audit,
    }
    _write_json(output_root / "burgers-qualification-gates.json", final)
    if not all(qualification_checks.values()):
        raise RuntimeError("Burgers qualification completed with a failed release gate")
    print(
        json.dumps(
            {
                "status": final["status"],
                "accepted_seeds": report["accepted_seeds"],
                "rejected_seeds": report["rejected_seeds"],
                "report": str(report_path),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-python", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--metric-approval", type=Path, required=True)
    parser.add_argument("--execution-approval", type=Path, required=True)
    args = parser.parse_args()
    execute(
        training_python=args.training_python,
        reference_root=args.reference_root,
        output_root=args.output_root,
        metric_approval_path=args.metric_approval,
        execution_approval_path=args.execution_approval,
    )


if __name__ == "__main__":
    main()

"""Governed AutoDL multi-seed qualification for the Re=100 lid cavity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import tarfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
SMOKE_ADAPTER_ROOT = REPOSITORY_ROOT / "validation" / "smoke"
sys.path.insert(0, str(ORCHESTRATOR_SRC))
sys.path.insert(0, str(SMOKE_ADAPTER_ROOT))

from pinn_strategy_system.assurance import (  # noqa: E402
    EvaluationBasisService,
    ExperimentGovernanceService,
    MetricDecisionService,
    PhysicalAuditService,
    RunValidationService,
)
from pinn_strategy_system.contracts import (  # noqa: E402
    AggregationPolicy,
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactCollectionSpec,
    ArtifactCollectionStatus,
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
    RunSubmissionStatus,
    RunValidationInput,
    SourceRef,
    SshConnectionProfile,
    UnitSystemContract,
)
from pinn_strategy_system.domain_metrics.navier_stokes import (  # noqa: E402
    LidDrivenCavityMetricProvider,
)
from pinn_strategy_system.execution import (  # noqa: E402
    AutoDlSshBackendConfig,
    AutoDlSshRunnerBackend,
    FieldData,
    ManifestFirstRunner,
    PredictionAnalyzer,
    SQLiteRunRegistry,
    SystemOpenSshRuntime,
    SystemOpenSshTransport,
)
from run_governed_pinn_smoke import (  # noqa: E402
    ForbiddenReplayBackend,
    _artifact,
    _sha256,
    _verify_artifact_reference,
)

WORKFLOW_ID = "lid-cavity-ns-qualification-20260717"
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
    "melt-region",
    "phase-change",
    "heat-transfer",
    "burgers",
    "poisson",
    "fem-default",
    "fem_default",
)


@dataclass(frozen=True)
class CompletedRemoteRun:
    manifest: RunManifest
    exit_code: int
    submission: dict[str, Any]
    monitoring: dict[str, Any]
    artifacts: dict[str, ArtifactRef]
    collection_directory: Path


def _write_json(path: Path, payload: Any) -> ArtifactRef:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite NS evidence: {path}")
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


def _source_ref(path: Path, symbol: str) -> SourceRef:
    return SourceRef(uri=path.as_uri(), sha256=_sha256(path), symbol=symbol)


def _approval() -> ApprovalRecord:
    source = (
        REPOSITORY_ROOT
        / "openspec"
        / "changes"
        / "productize-universal-pinn-strategy-system"
        / "approval-records"
        / "2026-07-17-peer-cases-and-lid-cavity-ns.md"
    )
    return ApprovalRecord(
        approval_id="lid-cavity-ns-user-approval-20260717",
        workflow_id=WORKFLOW_ID,
        kind=ApprovalKind.EXPERIMENT,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=datetime(2026, 7, 17, tzinfo=UTC),
        scope=(
            "Re=100 lid-cavity smoke and paired three-seed full qualification "
            "under the approved velocity metric policy"
        ),
        evidence_refs=(_artifact("lid-cavity-user-approval", source),),
    )


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
            convergence["medium_to_fine_velocity_relative_l2"]
            < convergence["coarse_to_medium_velocity_relative_l2"]
        ),
        "ghia_cross_validation": (
            convergence["grid_levels"][-1]["ghia"]["combined_centerline_rmse"]
            <= 0.03
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
    *, worker: Path, reference_fields: Path, reference_solver: Path
) -> tuple[UnitSystemContract, PhysicalModelAuthority, ReferenceEvidence, MetricContract]:
    worker_ref = _artifact("lid-cavity-worker-source", worker)
    reference_ref = _artifact("lid-cavity-converged-reference", reference_fields)
    unit_system = UnitSystemContract(
        unit_system_id="lid-cavity-dimensionless-v1",
        name="dimensionless unit-square incompressible cavity",
        quantity_units={
            "x_coordinate": "dimensionless",
            "y_coordinate": "dimensionless",
            "velocity": "dimensionless",
            "pressure": "dimensionless",
            "reynolds_number": "dimensionless",
            "kinematic_viscosity": "dimensionless",
        },
        source_refs=(_source_ref(worker, "case_contract"),),
        confirmed_by_user=True,
    )
    authority = PhysicalModelAuthority(
        authority_id="lid-cavity-re100-authority-v1",
        project_id="universal-pinn-peer-case-qualification",
        model_family="pinn",
        pde_family="steady-incompressible-navier-stokes",
        task_type="forward",
        governing_equation_refs=(_source_ref(worker, "pde_residual"),),
        boundary_condition_refs=(_source_ref(worker, "CavityNet.forward"),),
        initial_condition_refs=(),
        geometry_refs=(_source_ref(worker, "case_contract"),),
        parameter_source_refs=(_source_ref(worker, "REYNOLDS_NUMBER"),),
        output_channels=("u", "v", "p"),
        unit_system=unit_system,
        confirmed_by_user=True,
    )
    reference = ReferenceEvidence(
        reference_id="lid-cavity-openfoam-converged-re100-v1",
        authority_id=authority.authority_id,
        kind=ReferenceKind.NUMERICAL,
        artifact_ref=reference_ref,
        output_channels=("u", "v", "p"),
        coordinate_system="dimensionless-cartesian-unit-square",
        channel_units={"u": "1", "v": "1", "p": "1"},
        source_refs=(_source_ref(reference_solver, "finalize"),),
        test_case_only=True,
        limitations=(
            "Independent OpenFOAM-6 test reference for Re=100 only.",
            "Pressure comparisons are zero-mean or gradient based.",
        ),
    )
    metrics = MetricContract(
        contract_id="lid-cavity-user-confirmed-metric-policy-v1",
        physical_model_authority_ref=worker_ref,
        reference_evidence_refs=(reference_ref,),
        metrics=(
            MetricRule(
                name="ns_velocity_relative_l2",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="1",
            ),
            MetricRule(
                name="ns_velocity_vector_max_abs",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="1",
            ),
            MetricRule(
                name="ns_centerline_velocity_rmse",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="1",
            ),
            MetricRule(
                name="ns_wall_velocity_max_abs",
                role=MetricRole.HARD_CONSTRAINT,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.PHYSICAL_MODEL,
                threshold=1.0e-6,
                unit="1",
            ),
            MetricRule(
                name="ns_pressure_mean_abs",
                role=MetricRole.HARD_CONSTRAINT,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.PHYSICAL_MODEL,
                threshold=1.0e-6,
                unit="1",
            ),
            MetricRule(
                name="ns_continuity_rms",
                role=MetricRole.GUARDRAIL,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.PHYSICAL_MODEL,
                max_relative_regression=0.25,
                unit="1",
            ),
            MetricRule(
                name="ns_momentum_rms",
                role=MetricRole.GUARDRAIL,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.PHYSICAL_MODEL,
                max_relative_regression=0.25,
                unit="1",
            ),
            MetricRule(
                name="ns_pressure_gradient_relative_l2",
                role=MetricRole.GUARDRAIL,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                max_relative_regression=0.10,
                unit="1",
            ),
            MetricRule(
                name="ns_high_shear_velocity_rmse",
                role=MetricRole.GUARDRAIL,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                max_relative_regression=0.10,
                unit="1",
            ),
            MetricRule(
                name="ns_reference_shear_threshold",
                role=MetricRole.DIAGNOSTIC,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="1",
            ),
        ),
        primary_order=(
            "ns_velocity_relative_l2",
            "ns_velocity_vector_max_abs",
            "ns_centerline_velocity_rmse",
        ),
        aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
        acceptable_regression_notes=(
            "Continuity and momentum RMS may regress by at most 25 percent.",
            "Pressure-gradient and high-shear errors may regress by at most 10 percent.",
            "Wall velocity and zero-mean pressure gauge are hard constraints.",
        ),
    )
    return unit_system, authority, reference, metrics


def _physical_audit(worker: Path, unit_system: UnitSystemContract):
    rows = (
        ("x-lower", "x_min", "lower x coordinate", "x_coordinate", 0.0),
        ("x-upper", "x_max", "upper x coordinate", "x_coordinate", 1.0),
        ("y-lower", "y_min", "lower y coordinate", "y_coordinate", 0.0),
        ("y-upper", "y_max", "upper y coordinate", "y_coordinate", 1.0),
        ("lid-speed", "lid_speed", "moving-lid speed", "velocity", 1.0),
        ("reynolds", "REYNOLDS_NUMBER", "Reynolds number", "reynolds_number", 100.0),
        ("viscosity", "VISCOSITY", "kinematic viscosity", "kinematic_viscosity", 0.01),
    )
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
        for parameter_id, symbol, meaning, quantity_kind, value in rows
    )
    return PhysicalAuditService().audit(
        report_id="lid-cavity-physical-audit-v1",
        unit_system=unit_system,
        parameters=parameters,
    )


def _create_staging_archive(
    *, output: Path, worker: Path, reference_fields: Path
) -> ArtifactRef:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite staging archive: {output}")
    with tarfile.open(output, mode="x") as stream:
        stream.add(worker, arcname="cavity_pinn_worker.py", recursive=False)
        stream.add(reference_fields, arcname="reference_fields.npz", recursive=False)
    return _artifact("lid-cavity-staging-archive", output)


def _local_openssh_environment() -> tuple[tuple[str, str], ...]:
    allowed = (
        "COMSPEC",
        "HOME",
        "PATH",
        "PATHEXT",
        "PROGRAMDATA",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    )
    return tuple((name, os.environ[name]) for name in allowed if name in os.environ)


def _backend(arguments: argparse.Namespace, output_root: Path):
    profile = SshConnectionProfile(
        profile_id="autodl-a",
        host_key_fingerprint_sha256=arguments.host_fingerprint_sha256,
        identity_key_fingerprint_sha256=arguments.identity_fingerprint_sha256,
    )
    runtime = SystemOpenSshRuntime(
        profile_id=profile.profile_id,
        ssh_executable=arguments.ssh_executable.resolve(strict=True),
        scp_executable=arguments.scp_executable.resolve(strict=True),
        username=arguments.username,
        hostname=arguments.hostname,
        port=arguments.port,
        identity_file=arguments.identity_file.resolve(strict=True),
        known_hosts_file=arguments.known_hosts_file.resolve(strict=True),
        remote_python=arguments.remote_backend_python,
        local_working_directory=output_root,
        environment=_local_openssh_environment(),
        connect_timeout_seconds=15,
        operation_timeout_seconds=180,
    )
    remote_environment = (
        ("HOME", "/root"),
        (
            "PATH",
            f"{arguments.remote_training_python.parent}:"
            "/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/sbin:"
            "/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        ),
        ("PYTHONUTF8", "1"),
        ("PYTHONUNBUFFERED", "1"),
        ("CUBLAS_WORKSPACE_CONFIG", ":4096:8"),
    )
    config = AutoDlSshBackendConfig(
        connection_profile=profile,
        remote_root=arguments.remote_root,
        local_control_root=(output_root / "backend-control").resolve(strict=True),
        remote_environment=remote_environment,
        environment_allowlist=tuple(name for name, _ in remote_environment),
        heartbeat_interval_seconds=5.0,
        heartbeat_stale_after_seconds=45.0,
    )
    return AutoDlSshRunnerBackend(config, SystemOpenSshTransport(runtime))


def _manifest(
    *,
    staging_ref: ArtifactRef,
    remote_root: PurePosixPath,
    remote_python: PurePosixPath,
    run_name: str,
    mode: str,
    sampler: str,
    seed: int,
    focus: tuple[float, float],
) -> RunManifest:
    run_id = f"lid-cavity-{run_name}-20260717"
    workspace = remote_root / "runs" / run_id / "workspace"
    output = workspace / "output"
    command = (
        str(remote_python),
        str(workspace / "cavity_pinn_worker.py"),
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
        "--sigma",
        "0.10",
        "--device",
        "cuda",
        "--reference",
        str(workspace / "reference_fields.npz"),
        "--output",
        str(output),
    )
    return RunManifest(
        run_id=run_id,
        workflow_id=WORKFLOW_ID,
        experiment_id=f"lid-cavity-{run_name}-experiment-20260717",
        idempotency_key=f"lid-cavity-{run_name}-seed-{seed}-20260717",
        environment_name="pinn-ns-torch231-py311",
        interpreter=str(remote_python),
        working_directory=str(workspace),
        command=command,
        config_ref=staging_ref,
        output_root=str(output),
        expected_artifacts=EXPECTED_OUTPUTS,
        checkpoint_policy="Persist model, aligned fields, metrics and hashes.",
        rollback_plan="Retain paired baselines and every rejected seed.",
    )


def _run_remote(
    *,
    manifest: RunManifest,
    approval: ApprovalRecord,
    runner: ManifestFirstRunner,
    collection_directory: Path,
    timeout_seconds: float,
) -> CompletedRemoteRun:
    submission = runner.submit(manifest, approval)
    started = time.monotonic()
    observations = []
    terminal = {
        RunSubmissionStatus.COMPLETED,
        RunSubmissionStatus.FAILED,
        RunSubmissionStatus.CANCELLED,
    }
    while submission.status not in terminal:
        if time.monotonic() - started > timeout_seconds:
            raise TimeoutError(f"remote NS run timed out: {manifest.run_id}")
        time.sleep(5.0)
        submission = runner.reconcile(manifest.idempotency_key)
        status = submission.last_backend_status
        observations.append(
            {
                "observed_at": datetime.now(UTC).isoformat(),
                "submission_status": submission.status.value,
                "backend_phase": None if status is None else status.phase.value,
                "stdout_offset": (
                    None if status is None or status.log_cursor is None else status.log_cursor.stdout_offset
                ),
                "stderr_offset": (
                    None if status is None or status.log_cursor is None else status.log_cursor.stderr_offset
                ),
            }
        )
    status = submission.last_backend_status
    exit_code = -1 if status is None or status.exit_code is None else status.exit_code
    if submission.status is not RunSubmissionStatus.COMPLETED:
        raise RuntimeError(
            f"remote NS run failed: {manifest.run_id}, status={submission.status.value}"
        )
    if submission.backend_ref is None:
        raise RuntimeError("completed remote NS run has no backend reference")
    collection_directory.parent.mkdir(parents=True, exist_ok=True)
    submission = runner.collect(
        manifest.idempotency_key,
        ArtifactCollectionSpec(
            run_id=manifest.run_id,
            backend_ref=submission.backend_ref,
            destination_root=str(collection_directory),
            required_artifacts=manifest.expected_artifacts,
        ),
    )
    collection = submission.collection_report
    if collection is None or collection.status is not ArtifactCollectionStatus.COMPLETE:
        raise RuntimeError(f"remote NS collection failed: {manifest.run_id}")
    artifacts = {
        relative: _artifact(
            f"{manifest.run_id}-{relative.replace('/', '_')}",
            collection_directory / relative,
        )
        for relative in EXPECTED_OUTPUTS
    }
    return CompletedRemoteRun(
        manifest=manifest,
        exit_code=exit_code,
        submission=submission.model_dump(mode="json"),
        monitoring={
            "status": "COMPLETED",
            "observation_count": len(observations),
            "observations": observations,
        },
        artifacts=artifacts,
        collection_directory=collection_directory,
    )


def _field(run: CompletedRemoteRun) -> tuple[FieldData, FieldData, dict[str, np.ndarray]]:
    path = run.collection_directory / "aligned_fields.npz"
    with np.load(path, allow_pickle=False) as payload:
        arrays = {name: np.asarray(payload[name]) for name in payload.files}
    prediction = arrays["prediction_velocity"].astype(float)
    reference = arrays["reference_velocity"].astype(float)
    continuity = np.repeat(arrays["continuity"][:, :, None], 2, axis=2)
    pressure = np.repeat(arrays["prediction_p"][:, :, None], 2, axis=2)
    context_fields = {
        "continuity_residual": continuity,
        "momentum_residual": arrays["momentum"].astype(float),
        "pressure_field": pressure,
        "pressure_gradient": arrays["prediction_pressure_gradient"].astype(float),
        "reference_pressure_gradient": arrays["reference_pressure_gradient"].astype(float),
    }
    reference_identity = hashlib.sha256(reference.tobytes()).hexdigest()
    common = {
        "axes": ("y", "x", "channel"),
        "coordinates": {
            "y": arrays["y"].astype(float),
            "x": arrays["x"].astype(float),
            "channel": np.asarray(("u", "v")),
        },
        "reference_identity": reference_identity,
        "unit": "1",
        "coordinate_system": "dimensionless-cartesian-unit-square",
        "normalization": "physical",
    }
    return (
        FieldData(
            values=prediction,
            artifact_ref=run.artifacts["aligned_fields.npz"],
            context_fields=context_fields,
            **common,
        ),
        FieldData(
            values=reference,
            artifact_ref=run.artifacts["aligned_fields.npz"],
            **common,
        ),
        arrays,
    )


def _metric_values(report) -> dict[str, float]:
    return {
        **{name: float(value) for name, value in report.global_metrics.items()},
        **{name: float(value) for name, value in report.domain_metrics.items()},
    }


def _localized_vector_diagnosis(arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    error = arrays["prediction_velocity"] - arrays["reference_velocity"]
    magnitude = np.sqrt(np.sum(np.square(error), axis=2))
    y_index, x_index = np.unravel_index(int(np.argmax(magnitude)), magnitude.shape)
    x = arrays["x"].astype(float)
    y = arrays["y"].astype(float)
    center_x = int(np.argmin(np.abs(x - 0.5)))
    center_y = int(np.argmin(np.abs(y - 0.5)))
    u_center_error = np.abs(error[:, center_x, 0])
    v_center_error = np.abs(error[center_y, :, 1])
    du_dy, du_dx = np.gradient(arrays["reference_velocity"][:, :, 0], y, x, edge_order=2)
    dv_dy, dv_dx = np.gradient(arrays["reference_velocity"][:, :, 1], y, x, edge_order=2)
    shear = np.sqrt(
        np.square(du_dx) + np.square(du_dy) + np.square(dv_dx) + np.square(dv_dy)
    )
    threshold = float(np.percentile(shear, 90.0))
    high_shear_error = np.where(shear >= threshold, magnitude, -np.inf)
    shear_y, shear_x = np.unravel_index(int(np.argmax(high_shear_error)), shear.shape)
    return {
        "vector_max": {
            "x": float(x[x_index]),
            "y": float(y[y_index]),
            "absolute_error": float(magnitude[y_index, x_index]),
        },
        "vertical_centerline_u_max": {
            "x": float(x[center_x]),
            "y": float(y[int(np.argmax(u_center_error))]),
            "absolute_error": float(np.max(u_center_error)),
        },
        "horizontal_centerline_v_max": {
            "x": float(x[int(np.argmax(v_center_error))]),
            "y": float(y[center_y]),
            "absolute_error": float(np.max(v_center_error)),
        },
        "high_shear_max": {
            "x": float(x[shear_x]),
            "y": float(y[shear_y]),
            "absolute_error": float(magnitude[shear_y, shear_x]),
            "reference_shear_threshold": threshold,
        },
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
        experiment_id=f"lid-cavity-focused-seed-{seed}-20260717",
        project_id="universal-pinn-peer-case-qualification",
        observed_failure_mechanism=(
            f"localized velocity-vector error near x={focus[0]}, y={focus[1]}"
        ),
        supporting_evidence_refs=(diagnosis_ref,),
        interventions=(
            InterventionChange(
                target="fixed_collocation_sampler",
                before={"uniform_fraction": 1.0, "focused_fraction": 0.0},
                after={"uniform_fraction": 0.875, "focused_fraction": 0.125},
                rationale="Test one localized sampling change at the diagnosed vector-error peak.",
                source_ref=_source_ref(worker, "sample_points"),
            ),
        ),
        unchanged_controls=(
            "continuity and momentum equations, Re=100 and pressure gauge",
            "moving-lid and no-slip boundary transform",
            "converged OpenFOAM reference and evaluation grid",
            "network initialization and architecture",
            "optimizer, schedule, epoch budget and collocation count",
            f"random seed {seed} within the paired comparison",
        ),
        expected_primary_metric_movement={
            "ns_velocity_relative_l2": "decrease",
            "ns_velocity_vector_max_abs": "decrease when relative_l2 is tied",
            "ns_centerline_velocity_rmse": "decrease when earlier primaries tie",
        },
        guardrail_limits={
            "wall_velocity_max_abs": 1.0e-6,
            "pressure_mean_abs": 1.0e-6,
            "continuity_relative_regression": 0.25,
            "momentum_relative_regression": 0.25,
            "pressure_gradient_relative_regression": 0.10,
            "high_shear_relative_regression": 0.10,
        },
        smoke_budget=BudgetSpec(max_steps=20, resource_description="bounded AutoDL smoke"),
        full_budget=BudgetSpec(max_steps=6000, max_seconds=7200, resource_description="paired AutoDL GPU full run"),
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
        checkpoint_policy="Persist all model and field artifacts before comparison.",
        expected_artifacts=EXPECTED_OUTPUTS,
    )
    completeness = ExperimentGovernanceService().audit(
        report_id=f"lid-cavity-seed-{seed}-experiment-completeness",
        draft=draft,
    )
    if completeness.status is not AuditStatus.PASS:
        raise RuntimeError(f"NS experiment completeness failed for seed {seed}")
    return completeness


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
        "status": "PASS" if all(all(item.values()) for item in runs.values()) else "FAIL",
        "runs": runs,
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
        return tuple(text for child in value for text in _semantic_strings(child))
    return (value.casefold(),) if isinstance(value, str) else ()


def execute(arguments: argparse.Namespace) -> None:
    reference_root = arguments.reference_root.resolve(strict=True)
    output_root = arguments.output_root.resolve(strict=False)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite qualification root: {output_root}")
    worker = (Path(__file__).resolve().parent / "cavity_pinn_worker.py").resolve(strict=True)
    reference_solver = (Path(__file__).resolve().parent / "cavity_reference.py").resolve(strict=True)
    reference_gate = _reference_gate(reference_root)
    if reference_gate["status"] != "PASS":
        raise RuntimeError("lid-cavity reference is not decision-ready")
    output_root.mkdir(parents=True)
    (output_root / "backend-control").mkdir()
    (output_root / "collected").mkdir()
    evidence = output_root / "evidence"
    approval = _approval()
    staging_ref = _create_staging_archive(
        output=output_root / "staging" / "lid-cavity-worker-reference.tar",
        worker=worker,
        reference_fields=reference_gate["fields"],
    )
    source_ref = _write_json(
        evidence / "source-snapshot.json",
        {
            "worker": {"path": str(worker), "sha256": _sha256(worker)},
            "reference_solver": {
                "path": str(reference_solver),
                "sha256": _sha256(reference_solver),
            },
            "staging": staging_ref.model_dump(mode="json"),
        },
    )
    reference_ref = _artifact("lid-cavity-converged-reference", reference_gate["fields"])
    reference_gate_ref = _write_json(
        evidence / "reference-gate.json",
        {
            key: value
            for key, value in reference_gate.items()
            if key not in {"fields", "convergence_path", "manifest_path"}
        },
    )
    unit_system, authority, reference_evidence, metric_contract = _contracts(
        worker=worker,
        reference_fields=reference_gate["fields"],
        reference_solver=reference_solver,
    )
    physical = _physical_audit(worker, unit_system)
    basis = EvaluationBasisService().validate(
        authority=authority, references=(reference_evidence,)
    )
    if physical.status is not AuditStatus.PASS or not basis.ready:
        raise RuntimeError("lid-cavity physical audit or evaluation basis failed")
    physical_ref = _write_json(evidence / "physical-audit.json", physical.model_dump(mode="json"))
    metric_contract_ref = _write_json(
        evidence / "metric-contract.json", metric_contract.model_dump(mode="json")
    )
    registry_path = output_root / "launch-registry.sqlite3"
    runner = ManifestFirstRunner(
        SQLiteRunRegistry(registry_path), _backend(arguments, output_root)
    )
    manifests: list[RunManifest] = []
    provider = LidDrivenCavityMetricProvider()

    uniform_smoke_manifest = _manifest(
        staging_ref=staging_ref,
        remote_root=arguments.remote_root,
        remote_python=arguments.remote_training_python,
        run_name="uniform-smoke-seed-7",
        mode="smoke",
        sampler="uniform",
        seed=7,
        focus=(0.5, 0.5),
    )
    uniform_smoke = _run_remote(
        manifest=uniform_smoke_manifest,
        approval=approval,
        runner=runner,
        collection_directory=output_root / "collected" / "uniform-smoke-seed-7",
        timeout_seconds=900,
    )
    manifests.append(uniform_smoke_manifest)
    smoke_field, smoke_reference, _ = _field(uniform_smoke)
    smoke_analysis = PredictionAnalyzer().analyze(
        report_id="lid-cavity-uniform-smoke",
        prediction=smoke_field,
        reference=smoke_reference,
        domain_metric_providers=(provider,),
    )
    if smoke_analysis.status is not ResultStatus.VALID:
        raise RuntimeError("lid-cavity uniform smoke analysis failed")
    runtime_environment = json.loads(
        (uniform_smoke.collection_directory / "runtime_environment.json").read_text(encoding="utf-8")
    )
    environment_checks = {
        "python_3_11_11": runtime_environment["python"] == "3.11.11",
        "torch_2_3_1": str(runtime_environment["torch"]).startswith("2.3.1"),
        "numpy_2_2_5": runtime_environment["numpy"] == "2.2.5",
        "cuda_device": runtime_environment["device"] == "cuda",
        "gpu_recorded": bool(runtime_environment["gpu"]),
        "deterministic_algorithms": bool(
            runtime_environment["deterministic_algorithms"]
        ),
    }
    if not all(environment_checks.values()):
        raise RuntimeError(f"remote training environment gate failed: {environment_checks}")
    environment_ref = _write_json(
        evidence / "environment.json",
        {"runtime": runtime_environment, "checks": environment_checks},
    )

    focused_smoke_completed = False
    seed_reports = []
    for seed in FROZEN_SEEDS:
        baseline_manifest = _manifest(
            staging_ref=staging_ref,
            remote_root=arguments.remote_root,
            remote_python=arguments.remote_training_python,
            run_name=f"uniform-full-seed-{seed}",
            mode="full",
            sampler="uniform",
            seed=seed,
            focus=(0.5, 0.5),
        )
        baseline = _run_remote(
            manifest=baseline_manifest,
            approval=approval,
            runner=runner,
            collection_directory=output_root / "collected" / f"uniform-full-seed-{seed}",
            timeout_seconds=9000,
        )
        manifests.append(baseline_manifest)
        baseline_field, baseline_reference, baseline_arrays = _field(baseline)
        baseline_analysis = PredictionAnalyzer().analyze(
            report_id=f"lid-cavity-baseline-seed-{seed}",
            prediction=baseline_field,
            reference=baseline_reference,
            top_k=10,
            domain_metric_providers=(provider,),
        )
        if baseline_analysis.status is not ResultStatus.VALID:
            raise RuntimeError(f"lid-cavity baseline analysis failed for seed {seed}")
        diagnosis = _localized_vector_diagnosis(baseline_arrays)
        focus = (
            diagnosis["vector_max"]["x"],
            diagnosis["vector_max"]["y"],
        )
        diagnosis_ref = _write_json(
            evidence / f"baseline-diagnosis-seed-{seed}.json",
            {
                "prediction_analysis": baseline_analysis.model_dump(mode="json"),
                "velocity_localization": diagnosis,
            },
        )
        if not focused_smoke_completed:
            focused_smoke_manifest = _manifest(
                staging_ref=staging_ref,
                remote_root=arguments.remote_root,
                remote_python=arguments.remote_training_python,
                run_name="focused-smoke-seed-7",
                mode="smoke",
                sampler="focused",
                seed=7,
                focus=focus,
            )
            focused_smoke = _run_remote(
                manifest=focused_smoke_manifest,
                approval=approval,
                runner=runner,
                collection_directory=output_root / "collected" / "focused-smoke-seed-7",
                timeout_seconds=900,
            )
            manifests.append(focused_smoke_manifest)
            focused_field, focused_reference, _ = _field(focused_smoke)
            focused_analysis = PredictionAnalyzer().analyze(
                report_id="lid-cavity-focused-smoke",
                prediction=focused_field,
                reference=focused_reference,
                domain_metric_providers=(provider,),
            )
            if focused_analysis.status is not ResultStatus.VALID:
                raise RuntimeError("lid-cavity focused smoke analysis failed")
            focused_smoke_completed = True

        completeness = _governed_experiment(
            seed=seed,
            focus=focus,
            baseline_ref=baseline.artifacts["aligned_fields.npz"],
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
        candidate_manifest = _manifest(
            staging_ref=staging_ref,
            remote_root=arguments.remote_root,
            remote_python=arguments.remote_training_python,
            run_name=f"focused-full-seed-{seed}",
            mode="full",
            sampler="focused",
            seed=seed,
            focus=focus,
        )
        candidate = _run_remote(
            manifest=candidate_manifest,
            approval=approval,
            runner=runner,
            collection_directory=output_root / "collected" / f"focused-full-seed-{seed}",
            timeout_seconds=9000,
        )
        manifests.append(candidate_manifest)
        candidate_field, candidate_reference, candidate_arrays = _field(candidate)
        comparison = PredictionAnalyzer().compare(
            report_id=f"lid-cavity-comparison-seed-{seed}",
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
            decision_id=f"lid-cavity-decision-seed-{seed}",
            contract=metric_contract,
            baseline=MetricValueSet(subject_id=baseline_manifest.run_id, values=baseline_values),
            candidate=MetricValueSet(subject_id=candidate_manifest.run_id, values=candidate_values),
            observed_failure_mechanism="localized velocity error in the diagnosed high-shear flow",
        )
        decision_payload = decision.model_dump(mode="json")
        decision_payload.update(
            {
                "selected_intervention": (
                    "12.5 percent localized fixed collocation"
                    if decision.status is DecisionStatus.ACCEPT
                    else None
                ),
                "unchanged_controls": list(completeness.experiment_spec.unchanged_controls),
                "supporting_evidence_refs": [comparison_ref.model_dump(mode="json")],
                "expected_primary_metric_movement": dict(
                    completeness.experiment_spec.expected_primary_metric_movement
                ),
                "guardrail_limits": dict(completeness.experiment_spec.guardrail_limits),
                "falsification_condition": completeness.experiment_spec.falsification_condition,
                "rollback_plan": completeness.experiment_spec.rollback_plan,
            }
        )
        decision = DecisionRecord.model_validate(decision_payload)
        candidate_diagnosis = _localized_vector_diagnosis(candidate_arrays)
        evaluation = ModelEvaluationReport(
            report_id=f"lid-cavity-evaluation-seed-{seed}",
            status=comparison.status,
            physical_model_authority_ref=_artifact("lid-cavity-worker-authority", worker),
            metric_values=candidate_values,
            metric_bases={
                name: (
                    MetricEvidenceBasis.PHYSICAL_MODEL
                    if name.startswith("ns_continuity")
                    or name.startswith("ns_momentum")
                    or name.startswith("ns_wall")
                    or name.startswith("ns_pressure_mean")
                    else MetricEvidenceBasis.REFERENCE_EVIDENCE
                )
                for name in candidate_values
            },
            prediction_analysis_ref=comparison_ref,
            diagnostic_refs=(
                candidate.artifacts["aligned_fields.npz"],
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
                "source_unchanged": _sha256(worker)
                == json.loads((evidence / "source-snapshot.json").read_text(encoding="utf-8"))["worker"]["sha256"],
            },
        )
        manifest_ref = _write_json(
            evidence / f"candidate-manifest-seed-{seed}.json",
            candidate_manifest.model_dump(mode="json"),
        )
        validation = RunValidationService().validate(
            report_id=f"lid-cavity-validation-seed-{seed}",
            validation_input=RunValidationInput(
                run_id=candidate_manifest.run_id,
                process_exit_code=candidate.exit_code,
                physical_audit=physical,
                model_evaluation=evaluation,
                metric_decision=decision,
                required_artifacts=EXPECTED_OUTPUTS,
                produced_artifacts=candidate.artifacts,
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
            key: value for key, value in validation.checks.items() if key != "metric_decision"
        }
        seed_reports.append(
            {
                "seed": seed,
                "focus": {"x": focus[0], "y": focus[1]},
                "baseline_localization": diagnosis,
                "candidate_localization": candidate_diagnosis,
                "experiment_spec_ref": experiment_ref.model_dump(mode="json"),
                "baseline": comparison.baseline_report.model_dump(mode="json"),
                "candidate": comparison.candidate_report.model_dump(mode="json"),
                "metric_deltas": dict(comparison.metric_deltas),
                "decision": decision.model_dump(mode="json"),
                "validation": validation.model_dump(mode="json"),
                "validation_ref": validation_ref.model_dump(mode="json"),
                "evidence_integrity": {
                    "status": "PASS" if all(integrity_checks.values()) else "FAIL",
                    "checks": integrity_checks,
                },
                "process": {
                    "baseline": baseline.monitoring,
                    "candidate": candidate.monitoring,
                },
            }
        )

    replay = _replay(tuple(manifests), approval, registry_path)
    metric_names = (
        "ns_velocity_relative_l2",
        "ns_velocity_vector_max_abs",
        "ns_centerline_velocity_rmse",
        "ns_continuity_rms",
        "ns_momentum_rms",
    )
    uncertainty = {}
    for name in metric_names:
        values = [float(item["candidate"]["domain_metrics"][name]) for item in seed_reports]
        uncertainty[name] = {
            "mean": statistics.fmean(values),
            "sample_std": statistics.stdev(values),
            "min": min(values),
            "max": max(values),
        }
    report = {
        "workflow_id": WORKFLOW_ID,
        "case_id": "lid-driven-cavity-re100-v1",
        "peer_case_status": "SCIENTIFIC_PEER",
        "frozen_seeds": list(FROZEN_SEEDS),
        "predeclared_seed_policy": "No result-based omission or rerun.",
        "environment": {"runtime": runtime_environment, "checks": environment_checks},
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
            "focus_rule": "paired baseline velocity-vector maximum-error coordinate",
            "sigma": 0.10,
        },
        "smoke": {
            "uniform_status": smoke_analysis.status.value,
            "focused_status": "RESULT_VALID" if focused_smoke_completed else "RESULT_INVALID",
            "scientific_effectiveness_claimed": False,
        },
        "per_seed": seed_reports,
        "candidate_uncertainty": uncertainty,
        "accepted_seeds": [
            item["seed"] for item in seed_reports if item["decision"]["status"] == "ACCEPT"
        ],
        "rejected_seeds": [
            item["seed"] for item in seed_reports if item["decision"]["status"] != "ACCEPT"
        ],
        "replay": replay,
    }
    report_path = output_root / "lid-cavity-qualification-report.json"
    report_ref = _write_json(report_path, report)
    scan_paths = (
        evidence / "metric-contract.json",
        report_path,
        *(
            output_root / "collected" / f"focused-full-seed-{seed}" / "case_contract.json"
            for seed in FROZEN_SEEDS
        ),
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
        "policy_id": "lid-cavity-contract-isolation-v1",
        "status": "PASS" if not violations else "FAIL",
        "scanned_sha256": {str(path): _sha256(path) for path in scan_paths},
        "violation_count": sum(len(terms) for terms in violations.values()),
        "report_ref": report_ref.model_dump(mode="json"),
    }
    _write_json(output_root / "lid-cavity-semantic-isolation-audit.json", semantic_audit)
    provenance_refs = (
        source_ref,
        environment_ref,
        reference_ref,
        reference_gate_ref,
        physical_ref,
        metric_contract_ref,
        *(ArtifactRef.model_validate(item["validation_ref"]) for item in seed_reports),
    )
    provenance_valid = all(
        _verify_artifact_reference(item.model_dump(mode="json"))
        for item in provenance_refs
    )
    qualification_checks = {
        "reference": reference_gate["status"] == "PASS",
        "physical_audit": physical.status is AuditStatus.PASS,
        "evaluation_basis": basis.ready,
        "remote_environment": all(environment_checks.values()),
        "three_predeclared_seeds": len(seed_reports) == len(FROZEN_SEEDS),
        "all_seed_evidence_integrity": all(
            item["evidence_integrity"]["status"] == "PASS" for item in seed_reports
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
    _write_json(output_root / "lid-cavity-qualification-gates.json", final)
    if not all(qualification_checks.values()):
        raise RuntimeError("lid-cavity qualification completed with a failed release gate")
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
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ssh-executable", type=Path, required=True)
    parser.add_argument("--scp-executable", type=Path, required=True)
    parser.add_argument("--identity-file", type=Path, required=True)
    parser.add_argument("--known-hosts-file", type=Path, required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--remote-backend-python", type=PurePosixPath, required=True)
    parser.add_argument("--remote-training-python", type=PurePosixPath, required=True)
    parser.add_argument("--remote-root", type=PurePosixPath, required=True)
    parser.add_argument("--host-fingerprint-sha256", required=True)
    parser.add_argument("--identity-fingerprint-sha256", required=True)
    arguments = parser.parse_args()
    execute(arguments)


if __name__ == "__main__":
    main()

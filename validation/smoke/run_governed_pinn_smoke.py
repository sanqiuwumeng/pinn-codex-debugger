"""Execute and replay one governed, smoke-only PINN comparison.

The source case is never modified. Baseline and candidate are staged in
separate directories, launched through the manifest-first registry, monitored
through explicit process identities and evaluated with the existing universal
PINN contracts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
CASE_ADAPTER_ROOT = REPOSITORY_ROOT / "validation" / "cases"
sys.path.insert(0, str(ORCHESTRATOR_SRC))
sys.path.insert(0, str(CASE_ADAPTER_ROOT))

from pinn_strategy_system.assurance import (  # noqa: E402
    EventMonitor,
    ExperimentGovernanceService,
    RunValidationService,
)
from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactCollectionReport,
    ArtifactCollectionSpec,
    ArtifactCollectionStatus,
    ArtifactRef,
    AuditStatus,
    BackendRunPhase,
    BackendRunRef,
    BackendRunStatus,
    BudgetSpec,
    DecisionRecord,
    DecisionStatus,
    ExperimentDraft,
    ExecutionRequest,
    InterventionChange,
    MetricContract,
    MetricEvidenceBasis,
    ModelEvaluationReport,
    MonitorOutcome,
    MonitoringPolicy,
    PhysicalAuditReport,
    PreparedRun,
    ResultStatus,
    RunEvent,
    RunEventType,
    RunCancellationRequest,
    RunManifest,
    RunValidationInput,
    SourceRef,
    WorkflowIntent,
    WorkflowRequest,
    WorkflowStage,
    WorkflowStateEnvelope,
)
from pinn_strategy_system.execution import (  # noqa: E402
    ApprovedProcessIdentity,
    ApprovedProcessSampler,
    ExecutionBackend,
    LocalProcessBackendConfig,
    LocalProcessRunnerBackend,
    ManifestFirstRunner,
    ProcessUnavailableError,
    SQLiteRunRegistry,
)
from pinn_strategy_system.orchestration import build_phase0_graph  # noqa: E402
from pinn_strategy_system.storage import (  # noqa: E402
    AppendOnlyAuditStore,
    LocalArtifactStore,
    SQLiteCheckpointStore,
    StoreLayout,
)
from read_only_pinn_case import run_case  # noqa: E402

WORKFLOW_ID = "universal-pinn-smoke-20260716"
EXPERIMENT_ID = "focused-collocation-smoke-20260716"
PROJECT_ID = "pinn-2d-validation-case"
APPROVAL_ID = "approval-pinn-smoke-release-gates-20260716"
METRIC_APPROVAL_ID = "approval-pinn-metric-contract-20260716"
BASELINE_RUN_ID = "pinn2d-uniform-smoke-20260716"
CANDIDATE_RUN_ID = "pinn2d-focused-smoke-20260716"
BASELINE_TAG = "baseline_uniform_smoke_20260716"
CANDIDATE_TAG = "candidate_focused_smoke_20260716"

CASE_FILES = (
    "config.py",
    "fem_solver.py",
    "metrics.py",
    "physics.py",
    "run_benchmark.py",
    "visualization.py",
)
EXPECTED_OUTPUTS = (
    "benchmark_config.json",
    "field_metrics.json",
    "closed_loop_validation.json",
    "runtime_environment.json",
    "reproducibility_manifest.json",
    "data/aligned_fields.npz",
    "models/hard_bc_pinn_model.pth",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact(artifact_id: str, path: Path) -> ArtifactRef:
    resolved = path.resolve(strict=True)
    return ArtifactRef(
        artifact_id=artifact_id,
        uri=resolved.as_uri(),
        sha256=_sha256(resolved),
        size_bytes=resolved.stat().st_size,
    )


def _write_json_no_overwrite(path: Path, payload: Any) -> ArtifactRef:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    )
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.write("\n")
    return _artifact(path.stem, path)


def _source_snapshot(case_root: Path) -> dict[str, str]:
    paths = tuple(case_root / name for name in CASE_FILES) + (
        case_root / "pinn_model.py",
        case_root / "pinn_model.py_backup_2026-06-03",
    )
    return {str(path.resolve(strict=True)): _sha256(path) for path in paths}


def _stage_case(case_root: Path, destination: Path, model_source: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for name in CASE_FILES:
        shutil.copy2(case_root / name, destination / name)
    shutil.copy2(model_source, destination / "pinn_model.py")


def _environment_manifest(training_python: Path) -> dict[str, Any]:
    probe = (
        "import json,platform,sys,torch,numpy,scipy,matplotlib;"
        "print(json.dumps({"
        "'python':sys.version.split()[0],"
        "'executable':sys.executable,"
        "'platform':platform.platform(),"
        "'torch':torch.__version__,"
        "'cuda_available':torch.cuda.is_available(),"
        "'numpy':numpy.__version__,"
        "'scipy':scipy.__version__,"
        "'matplotlib':matplotlib.__version__},sort_keys=True))"
    )
    completed = subprocess.run(
        (str(training_python), "-c", probe),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(completed.stdout)
    if payload["python"] != "3.11.11" or not payload["torch"].startswith("2.3.1"):
        raise RuntimeError("smoke requires Python 3.11.11 and PyTorch 2.3.1")
    return payload


def _local_execution_environment() -> tuple[tuple[str, str], ...]:
    allowed_names = (
        "APPDATA",
        "COMSPEC",
        "CUDA_DEVICE_ORDER",
        "CUDA_PATH",
        "CUDA_VISIBLE_DEVICES",
        "HOME",
        "KMP_DUPLICATE_LIB_OK",
        "LD_LIBRARY_PATH",
        "LOCALAPPDATA",
        "MKL_NUM_THREADS",
        "MPLCONFIGDIR",
        "NVIDIA_VISIBLE_DEVICES",
        "OMP_NUM_THREADS",
        "PATH",
        "PATHEXT",
        "PROGRAMDATA",
        "PYTHONHASHSEED",
        "PYTHONUTF8",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TORCH_HOME",
        "USERPROFILE",
        "WINDIR",
        "XDG_CACHE_HOME",
    )
    environment = tuple(
        (name, os.environ[name])
        for name in allowed_names
        if name in os.environ
    )
    if "PYTHONUTF8" not in {name for name, _ in environment}:
        environment += (("PYTHONUTF8", "1"),)
    return environment


def _build_local_backend(run_root: Path) -> LocalProcessRunnerBackend:
    environment = _local_execution_environment()
    launcher_interpreter = Path(sys.executable).absolute()
    if not launcher_interpreter.is_file():
        raise ValueError("local backend launcher interpreter must be a file")
    return LocalProcessRunnerBackend(
        LocalProcessBackendConfig(
            run_root=run_root,
            launcher_interpreter=launcher_interpreter,
            environment=environment,
            environment_allowlist=tuple(name for name, _ in environment),
            heartbeat_interval_seconds=0.5,
            heartbeat_stale_after_seconds=10.0,
            cancellation_timeout_seconds=10.0,
        )
    )


class ForbiddenReplayBackend(ExecutionBackend):
    def __init__(self) -> None:
        self.launch_count = 0

    def prepare(self, request: ExecutionRequest) -> PreparedRun:
        self.launch_count += 1
        raise AssertionError(
            f"replay attempted to prepare {request.manifest.run_id}"
        )

    def launch(self, prepared_run: PreparedRun) -> BackendRunRef:
        self.launch_count += 1
        raise AssertionError(
            f"replay attempted to relaunch {prepared_run.request.manifest.run_id}"
        )

    def reconcile(self, backend_ref: BackendRunRef) -> BackendRunStatus:
        raise AssertionError(f"replay attempted to reconcile {backend_ref.run_id}")

    def cancel(
        self,
        backend_ref: BackendRunRef,
        request: RunCancellationRequest,
    ) -> BackendRunStatus:
        raise AssertionError(f"replay attempted to cancel {backend_ref.run_id}")

    def collect(
        self,
        backend_ref: BackendRunRef,
        spec: ArtifactCollectionSpec,
    ) -> ArtifactCollectionReport:
        raise AssertionError(f"replay attempted to collect {backend_ref.run_id}")


@dataclass(frozen=True)
class CompletedRun:
    manifest: RunManifest
    exit_code: int
    submission: dict[str, Any]
    monitoring: dict[str, Any]
    artifacts: dict[str, ArtifactRef]
    events: tuple[RunEvent, ...]


def _event(
    *,
    event_id: str,
    run_id: str,
    event_type: RunEventType,
    payload: dict[str, Any] | None = None,
    artifacts: tuple[ArtifactRef, ...] = (),
) -> RunEvent:
    return RunEvent(
        event_id=event_id,
        run_id=run_id,
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        payload=payload or {},
        artifact_refs=artifacts,
    )


def _run_one(
    *,
    manifest: RunManifest,
    approval: ApprovalRecord,
    runner: ManifestFirstRunner,
    audit: AppendOnlyAuditStore,
    output_directory: Path,
    collection_directory: Path,
    expected_outputs: tuple[str, ...] = EXPECTED_OUTPUTS,
) -> CompletedRun:
    events: list[RunEvent] = [
        _event(
            event_id=f"{manifest.run_id}-queued",
            run_id=manifest.run_id,
            event_type=RunEventType.RUN_QUEUED,
        )
    ]
    submission = runner.submit(manifest, approval)
    sampler: ApprovedProcessSampler | None = None
    startup_deadline = time.monotonic() + 30.0
    sample_index = 0
    terminal = (
        BackendRunPhase.COMPLETED,
        BackendRunPhase.FAILED,
        BackendRunPhase.CANCELLED,
    )
    while True:
        submission = runner.reconcile(manifest.idempotency_key)
        status = submission.last_backend_status
        if status is None:
            raise RuntimeError("local backend reconciliation returned no status")
        if (
            sampler is None
            and status.checks.get("process_identity_recorded", False)
            and status.process_id is not None
            and status.process_create_time is not None
        ):
            identity = ApprovedProcessIdentity(
                run_id=manifest.run_id,
                pid=status.process_id,
                expected_create_time=status.process_create_time,
                approval_id=approval.approval_id,
            )
            sampler = ApprovedProcessSampler((identity,))
            events.append(
                _event(
                    event_id=f"{manifest.run_id}-started",
                    run_id=manifest.run_id,
                    event_type=RunEventType.RUN_STARTED,
                    payload={
                        "pid": status.process_id,
                        "approval_id": approval.approval_id,
                    },
                )
            )
        if status.phase in terminal:
            break
        if sampler is not None:
            try:
                events.append(
                    sampler.capture(
                        event_id=(
                            f"{manifest.run_id}-resource-{sample_index}"
                        ),
                        run_id=manifest.run_id,
                        occurred_at=datetime.now(UTC),
                    )
                )
                sample_index += 1
            except ProcessUnavailableError:
                pass
        elif time.monotonic() > startup_deadline:
            raise RuntimeError("local backend did not record a target process identity")
        time.sleep(0.5)
    exit_code = status.exit_code if status.exit_code is not None else -1

    artifact_directory = output_directory
    if status.phase is BackendRunPhase.COMPLETED:
        if submission.backend_ref is None:
            raise RuntimeError("completed local run has no backend reference")
        submission = runner.collect(
            manifest.idempotency_key,
            ArtifactCollectionSpec(
                run_id=manifest.run_id,
                backend_ref=submission.backend_ref,
                destination_root=str(collection_directory),
                required_artifacts=manifest.expected_artifacts,
            ),
        )
        report = submission.collection_report
        if (
            report is None
            or report.status is not ArtifactCollectionStatus.COMPLETE
        ):
            raise RuntimeError("local backend artifact collection was not complete")
        artifact_directory = collection_directory

    artifacts: dict[str, ArtifactRef] = {}
    for relative in expected_outputs:
        path = artifact_directory / Path(relative)
        if path.exists():
            key = relative.replace("/", "_")
            artifacts[relative] = _artifact(f"{manifest.run_id}-{key}", path)

    if submission.prepared_run is None:
        raise RuntimeError("local run has no prepared-run evidence")
    run_directory = Path(submission.prepared_run.staging_root)
    log_paths = tuple(
        run_directory / f"{stream}.log"
        for stream in ("stdout", "stderr")
    )
    combined_log = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in log_paths
        if path.is_file()
    )
    lowered = combined_log.lower()
    if "out of memory" in lowered:
        events.append(
            _event(
                event_id=f"{manifest.run_id}-oom",
                run_id=manifest.run_id,
                event_type=RunEventType.GPU_OOM,
            )
        )
    if "nan" in lowered:
        events.append(
            _event(
                event_id=f"{manifest.run_id}-nan",
                run_id=manifest.run_id,
                event_type=RunEventType.NAN_DETECTED,
            )
        )

    metrics_path = output_directory / "field_metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        for index, (name, value) in enumerate(sorted(metrics.items())):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                events.append(
                    _event(
                        event_id=f"{manifest.run_id}-metric-{index}",
                        run_id=manifest.run_id,
                        event_type=RunEventType.METRIC_UPDATED,
                        payload={"metric": name, "value": float(value)},
                    )
                )

    checkpoint = artifacts.get("models/hard_bc_pinn_model.pth")
    if checkpoint is not None:
        events.append(
            _event(
                event_id=f"{manifest.run_id}-checkpoint",
                run_id=manifest.run_id,
                event_type=RunEventType.CHECKPOINT_WRITTEN,
                artifacts=(checkpoint,),
            )
        )
    events.append(
        _event(
            event_id=f"{manifest.run_id}-finished",
            run_id=manifest.run_id,
            event_type=(
                RunEventType.RUN_FINISHED
                if status.phase is BackendRunPhase.COMPLETED
                else RunEventType.RUN_FAILED
            ),
            payload={
                "exit_code": exit_code,
                "backend_phase": status.phase.value,
            },
            artifacts=tuple(artifacts.values()),
        )
    )

    required_ids = tuple(
        f"{manifest.run_id}-{name.replace('/', '_')}"
        for name in expected_outputs
    )
    monitoring = EventMonitor().evaluate(
        report_id=f"{manifest.run_id}-monitoring",
        run_id=manifest.run_id,
        events=tuple(events),
        policy=MonitoringPolicy(
            policy_id="pinn-smoke-process-policy",
            log_stall_seconds=60,
            required_artifact_ids=required_ids,
        ),
        now=datetime.now(UTC),
    )
    for run_event in events:
        audit.append(
            record_id=run_event.event_id,
            subject_id=manifest.run_id,
            category="run_event",
            occurred_at=run_event.occurred_at,
            payload=run_event,
        )
    audit.append(
        record_id=f"{manifest.run_id}-monitoring-report",
        subject_id=manifest.run_id,
        category="monitoring_report",
        occurred_at=datetime.now(UTC),
        payload=monitoring,
    )
    return CompletedRun(
        manifest=manifest,
        exit_code=exit_code,
        submission=submission.model_dump(mode="json"),
        monitoring=monitoring.model_dump(mode="json"),
        artifacts=artifacts,
        events=tuple(events),
    )


def _manifest(
    *,
    run_id: str,
    tag: str,
    workspace: Path,
    training_python: Path,
    config_ref: ArtifactRef,
) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        workflow_id=WORKFLOW_ID,
        experiment_id=EXPERIMENT_ID,
        idempotency_key=f"{EXPERIMENT_ID}-{tag}",
        environment_name="pytorch2.3.1",
        interpreter=str(training_python),
        working_directory=str(workspace),
        command=(
            str(training_python),
            str(workspace / "run_benchmark.py"),
            "--mode",
            "smoke",
            "--output-tag",
            tag,
        ),
        config_ref=config_ref,
        output_root=str(workspace / "outputs" / tag),
        expected_artifacts=EXPECTED_OUTPUTS,
        checkpoint_policy="Write the smoke model and reproducibility manifest.",
        rollback_plan="Preserve evidence, keep the uniform baseline active and do not promote the candidate.",
    )


def _pre_run_evidence(
    prior_report: dict[str, Any],
    authority_ref: ArtifactRef,
    analysis_ref: ArtifactRef,
) -> tuple[PhysicalAuditReport, MetricContract, ModelEvaluationReport]:
    metrics = prior_report["prediction_analysis"]["candidate_global_metrics"]
    physical = PhysicalAuditReport(
        report_id="pinn2d-prerun-physical-audit",
        unit_system_id="pinn-2d-test-case-si",
        status=AuditStatus.PASS,
        source_files_unchanged=True,
    )
    contract = MetricContract.model_validate(
        prior_report["metric_gate"]["contract"]
    )
    evaluation = ModelEvaluationReport(
        report_id="pinn2d-prerun-model-evaluation",
        status=ResultStatus.VALID,
        physical_model_authority_ref=authority_ref,
        metric_values={name: float(value) for name, value in metrics.items()},
        metric_bases={
            name: MetricEvidenceBasis.REFERENCE_EVIDENCE
            for name in metrics
        },
        prediction_analysis_ref=analysis_ref,
        domain_provider_ids=("heat-transfer.phase-change.v1",),
        checks={
            "physical_audit": True,
            "reference_compatibility": True,
            "aligned_fields": True,
        },
    )
    return physical, contract, evaluation


def execute(*, case_root: Path, training_python: Path, output_root: Path) -> None:
    case_root = case_root.resolve(strict=True)
    training_python = training_python.resolve(strict=True)
    output_root = output_root.resolve(strict=False)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite smoke root: {output_root}")
    output_root.mkdir(parents=True)

    original_snapshot = _source_snapshot(case_root)
    baseline_workspace = output_root / "workspaces" / "baseline"
    candidate_workspace = output_root / "workspaces" / "candidate"
    _stage_case(
        case_root,
        baseline_workspace,
        case_root / "pinn_model.py_backup_2026-06-03",
    )
    _stage_case(
        case_root,
        candidate_workspace,
        case_root / "pinn_model.py",
    )

    knowledge_root = output_root / "knowledge-source"
    knowledge_root.mkdir()
    layout = StoreLayout.provision(
        runtime_root=output_root / "runtime",
        knowledge_source_root=knowledge_root,
    )
    artifact_store = LocalArtifactStore(layout.artifact_root)
    audit = AppendOnlyAuditStore(layout.audit_database)
    backend_run_root = output_root / "backend-runs"
    backend_run_root.mkdir()
    collection_root = output_root / "collected-runs"
    collection_root.mkdir()

    source_manifest = {
        "case_root": str(case_root),
        "source_hashes": original_snapshot,
        "staged_baseline_model_sha256": _sha256(
            baseline_workspace / "pinn_model.py"
        ),
        "staged_candidate_model_sha256": _sha256(
            candidate_workspace / "pinn_model.py"
        ),
        "single_intervention": "sample_fixed_collocation",
    }
    source_ref = artifact_store.put_json("source-snapshot", source_manifest)
    environment_ref = artifact_store.put_json(
        "training-environment",
        _environment_manifest(training_python),
    )
    approval_path = (
        REPOSITORY_ROOT
        / "openspec"
        / "changes"
        / "build-rag-multi-agent-dl-strategy-system"
        / "approval-records"
        / "2026-07-16-pinn-smoke-release-gates.md"
    )
    approval_evidence_ref = _artifact("pinn-smoke-approval", approval_path)
    prior_report_path = (
        REPOSITORY_ROOT
        / "validation"
        / "cases"
        / "read-only-general-pinn-case-final-2026-07-16.json"
    )
    prior_report = json.loads(prior_report_path.read_text(encoding="utf-8"))
    prior_report_ref = _artifact("readonly-pinn-decision-evidence", prior_report_path)
    metric_contract_ref = artifact_store.put_json(
        "metric-contract",
        prior_report["metric_gate"]["contract"],
    )
    authority_ref = _artifact(
        "pinn2d-physical-model-authority",
        candidate_workspace / "physics.py",
    )

    draft = ExperimentDraft(
        experiment_id=EXPERIMENT_ID,
        project_id=PROJECT_ID,
        observed_failure_mechanism="localized early top-center reference-backed error",
        supporting_evidence_refs=(prior_report_ref,),
        interventions=(
            InterventionChange(
                target="sample_fixed_collocation",
                before={"uniform_fraction": 1.0, "focused_fraction": 0.0},
                after={"uniform_fraction": 0.875, "focused_fraction": 0.125},
                rationale="Test whether focused early top-center sampling reduces the localized maximum error.",
                source_ref=SourceRef(
                    uri=(candidate_workspace / "pinn_model.py").as_uri(),
                    sha256=_sha256(candidate_workspace / "pinn_model.py"),
                    symbol="sample_fixed_collocation",
                ),
            ),
        ),
        unchanged_controls=(
            "physics and units",
            "network architecture",
            "optimizer and learning rate",
            "eight smoke epochs",
            "FEM discretization",
            "random seed 42",
        ),
        expected_primary_metric_movement={
            "max_abs": "decrease",
            "rmse": "decrease if max_abs is tied",
        },
        guardrail_limits={
            "mae_absolute_regression_K": 1.0,
            "mae_relative_regression": 0.10,
        },
        smoke_budget=BudgetSpec(
            max_steps=8,
            max_seconds=180,
            resource_description="local CPU smoke in the existing PyTorch 2.3.1 environment",
        ),
        full_budget=BudgetSpec(
            max_steps=3000,
            resource_description="not authorized in this workflow",
        ),
        falsification_condition="Reject or roll back when the lexicographic metric contract or any assurance gate fails.",
        rollback_plan="Keep the uniform baseline active; preserve candidate evidence without promotion.",
        source_snapshot_ref=source_ref,
        dataset_refs=(authority_ref,),
        environment_ref=environment_ref,
        random_seed=42,
        baseline_run_ref=prior_report_ref,
        metric_contract_ref=metric_contract_ref,
        output_root=str(output_root),
        checkpoint_policy="Persist graph state and run manifests before launch; save smoke checkpoints.",
        expected_artifacts=EXPECTED_OUTPUTS,
    )
    completeness = ExperimentGovernanceService().audit(
        report_id="pinn2d-smoke-completeness",
        draft=draft,
    )
    if completeness.status is not AuditStatus.PASS:
        raise RuntimeError(f"experiment completeness failed: {completeness}")
    assert completeness.experiment_spec is not None
    experiment_ref = artifact_store.put_json(
        "experiment-spec",
        completeness.experiment_spec.model_dump(mode="json"),
    )

    experiment_approval = ApprovalRecord(
        approval_id=APPROVAL_ID,
        workflow_id=WORKFLOW_ID,
        kind=ApprovalKind.EXPERIMENT,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=datetime(2026, 7, 16, tzinfo=UTC),
        scope="OpenSpec tasks 8.4-8.6; smoke only; no full run",
        evidence_refs=(approval_evidence_ref,),
    )
    metric_approval = ApprovalRecord(
        approval_id=METRIC_APPROVAL_ID,
        workflow_id=WORKFLOW_ID,
        kind=ApprovalKind.METRIC_PRIORITY,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=datetime(2026, 7, 16, tzinfo=UTC),
        scope="max_abs then RMSE; MAE regression no more than 1.0 K and 10 percent",
        evidence_refs=(metric_contract_ref,),
    )
    prior_analysis_ref = prior_report_ref
    physical, metric_contract, pre_run_evaluation = _pre_run_evidence(
        prior_report,
        authority_ref,
        prior_analysis_ref,
    )
    request = WorkflowRequest(
        request_id="request-pinn2d-smoke-20260716",
        workflow_id=WORKFLOW_ID,
        project_id=PROJECT_ID,
        objective="Validate one focused-collocation strategy with smoke-only execution.",
        intent=WorkflowIntent.SMOKE,
        snapshot_ref=source_ref,
        requested_by="user",
    )
    initial_state = WorkflowStateEnvelope(
        workflow_id=WORKFLOW_ID,
        request=request,
        physical_audit=physical,
        metric_contract=metric_contract,
        model_evaluation=pre_run_evaluation,
        experiment_spec=completeness.experiment_spec,
        approvals=(metric_approval, experiment_approval),
        artifact_refs=(source_ref, environment_ref, experiment_ref),
    ).to_state()
    graph_config = {"configurable": {"thread_id": WORKFLOW_ID}}
    checkpoint_store = SQLiteCheckpointStore(layout.checkpoint_database)
    with checkpoint_store.open() as checkpointer:
        graph = build_phase0_graph(checkpointer)
        graph_result = graph.invoke(initial_state, graph_config)
    if graph_result["stage"] != WorkflowStage.SMOKE_APPROVED.value:
        raise RuntimeError(f"graph did not approve smoke: {graph_result['stage']}")

    registry_path = layout.tracking_database.parent / "launch_registry.sqlite3"
    registry = SQLiteRunRegistry(registry_path)
    backend = _build_local_backend(backend_run_root)
    runner = ManifestFirstRunner(registry, backend)
    baseline_manifest = _manifest(
        run_id=BASELINE_RUN_ID,
        tag=BASELINE_TAG,
        workspace=baseline_workspace,
        training_python=training_python,
        config_ref=_artifact("baseline-smoke-config-code", baseline_workspace / "config.py"),
    )
    candidate_manifest = _manifest(
        run_id=CANDIDATE_RUN_ID,
        tag=CANDIDATE_TAG,
        workspace=candidate_workspace,
        training_python=training_python,
        config_ref=_artifact("candidate-smoke-config-code", candidate_workspace / "config.py"),
    )
    baseline_manifest_ref = artifact_store.put_json(
        "baseline-run-manifest", baseline_manifest.model_dump(mode="json")
    )
    candidate_manifest_ref = artifact_store.put_json(
        "candidate-run-manifest", candidate_manifest.model_dump(mode="json")
    )
    baseline_run = _run_one(
        manifest=baseline_manifest,
        approval=experiment_approval,
        runner=runner,
        audit=audit,
        output_directory=baseline_workspace / "outputs" / BASELINE_TAG,
        collection_directory=collection_root / BASELINE_RUN_ID,
    )
    candidate_run = _run_one(
        manifest=candidate_manifest,
        approval=experiment_approval,
        runner=runner,
        audit=audit,
        output_directory=candidate_workspace / "outputs" / CANDIDATE_TAG,
        collection_directory=collection_root / CANDIDATE_RUN_ID,
    )
    if baseline_run.exit_code != 0 or candidate_run.exit_code != 0:
        raise RuntimeError("one or more smoke processes failed")

    copied_baseline = candidate_workspace / "outputs" / BASELINE_TAG
    shutil.copytree(
        baseline_workspace / "outputs" / BASELINE_TAG,
        copied_baseline,
    )
    analysis = run_case(
        case_root=candidate_workspace,
        baseline_name=BASELINE_TAG,
        candidate_name=CANDIDATE_TAG,
    )
    analysis_ref = artifact_store.put_json("smoke-analysis", analysis)
    decision_status = DecisionStatus(analysis["metric_gate"]["status"])
    candidate_metrics = analysis["prediction_analysis"]["candidate_global_metrics"]
    model_evaluation = ModelEvaluationReport(
        report_id="pinn2d-smoke-model-evaluation",
        status=ResultStatus(analysis["prediction_analysis"]["status"]),
        physical_model_authority_ref=authority_ref,
        metric_values={name: float(value) for name, value in candidate_metrics.items()},
        metric_bases={
            name: MetricEvidenceBasis.REFERENCE_EVIDENCE
            for name in candidate_metrics
        },
        prediction_analysis_ref=analysis_ref,
        diagnostic_refs=(candidate_run.artifacts["data/aligned_fields.npz"],),
        domain_provider_ids=("heat-transfer.phase-change.v1",),
        checks={
            "physical_audit": analysis["physical_audit"]["status"] == "PASS",
            "evaluation_basis": analysis["case_scope"]["evaluation_basis"]["ready"],
            "field_alignment": analysis["prediction_analysis"]["status"] == "RESULT_VALID",
            "source_integrity": analysis["read_only"]["all_observed_sources_unchanged"],
        },
    )
    decision = DecisionRecord(
        decision_id="pinn2d-smoke-metric-decision",
        status=decision_status,
        observed_failure_mechanism="localized early top-center reference-backed error",
        selected_intervention=(
            "12.5 percent focused collocation"
            if decision_status is DecisionStatus.ACCEPT
            else None
        ),
        unchanged_controls=completeness.experiment_spec.unchanged_controls,
        supporting_evidence_refs=(analysis_ref,),
        expected_primary_metric_movement=completeness.experiment_spec.expected_primary_metric_movement,
        guardrail_limits=completeness.experiment_spec.guardrail_limits,
        falsification_condition=completeness.experiment_spec.falsification_condition,
        rollback_plan=completeness.experiment_spec.rollback_plan,
        reasons=tuple(analysis["metric_gate"]["reasons"]),
    )
    candidate_validation = RunValidationService().validate(
        report_id="pinn2d-smoke-run-validation",
        validation_input=RunValidationInput(
            run_id=CANDIDATE_RUN_ID,
            process_exit_code=candidate_run.exit_code,
            physical_audit=physical,
            model_evaluation=model_evaluation,
            metric_decision=decision,
            required_artifacts=EXPECTED_OUTPUTS,
            produced_artifacts=candidate_run.artifacts,
            run_manifest_ref=candidate_manifest_ref,
            source_snapshot_ref=source_ref,
            dataset_refs=(authority_ref,),
            environment_ref=environment_ref,
            random_seed=42,
        ),
    )
    validation_ref = artifact_store.put_json(
        "candidate-validation",
        candidate_validation.model_dump(mode="json"),
    )
    source_unchanged = original_snapshot == _source_snapshot(case_root)
    rollback_required = (
        baseline_run.monitoring["outcome"] != MonitorOutcome.COMPLETED.value
        or candidate_run.monitoring["outcome"] != MonitorOutcome.COMPLETED.value
        or decision_status is not DecisionStatus.ACCEPT
        or candidate_validation.status is not ResultStatus.VALID
        or not source_unchanged
    )
    evidence_manifest = {
        "source_snapshot": source_ref.model_dump(mode="json"),
        "environment": environment_ref.model_dump(mode="json"),
        "experiment_spec": experiment_ref.model_dump(mode="json"),
        "baseline_manifest": baseline_manifest_ref.model_dump(mode="json"),
        "candidate_manifest": candidate_manifest_ref.model_dump(mode="json"),
        "analysis": analysis_ref.model_dump(mode="json"),
        "candidate_validation": validation_ref.model_dump(mode="json"),
        "baseline_outputs": {
            key: value.model_dump(mode="json")
            for key, value in baseline_run.artifacts.items()
        },
        "candidate_outputs": {
            key: value.model_dump(mode="json")
            for key, value in candidate_run.artifacts.items()
        },
    }
    evidence_ref = artifact_store.put_json("evidence-manifest", evidence_manifest)
    report = {
        "workflow_id": WORKFLOW_ID,
        "scope": "smoke only; no full run",
        "execution_location": "local exact-version training sandbox",
        "graph_stage": graph_result["stage"],
        "completeness": completeness.model_dump(mode="json"),
        "baseline": {
            "submission": baseline_run.submission,
            "exit_code": baseline_run.exit_code,
            "monitoring": baseline_run.monitoring,
        },
        "candidate": {
            "submission": candidate_run.submission,
            "exit_code": candidate_run.exit_code,
            "monitoring": candidate_run.monitoring,
            "validation": candidate_validation.model_dump(mode="json"),
        },
        "localized_analysis": {
            "baseline_global_metrics": analysis["prediction_analysis"]["baseline_global_metrics"],
            "candidate_global_metrics": analysis["prediction_analysis"]["candidate_global_metrics"],
            "baseline_max_abs": analysis["prediction_analysis"]["baseline_max_abs"],
            "candidate_max_abs": analysis["prediction_analysis"]["candidate_max_abs"],
            "baseline_roi_metrics": analysis["prediction_analysis"]["baseline_roi_metrics"],
            "candidate_roi_metrics": analysis["prediction_analysis"]["candidate_roi_metrics"],
            "error_migrated": analysis["prediction_analysis"]["error_migrated"],
        },
        "metric_decision": decision.model_dump(mode="json"),
        "rollback_evaluation": {
            "required": rollback_required,
            "action": (
                "keep uniform baseline active; preserve candidate evidence without promotion"
                if rollback_required
                else "candidate is smoke-valid but remains ineligible for full execution without new approval"
            ),
        },
        "source_case_unchanged": source_unchanged,
        "evidence_manifest_ref": evidence_ref.model_dump(mode="json"),
        "replay_status": "PENDING",
    }
    report_path = output_root / "smoke-execution-report.json"
    _write_json_no_overwrite(report_path, report)
    print(
        json.dumps(
            {
                "report": str(report_path),
                "decision": decision_status.value,
                "rollback_required": rollback_required,
                "source_unchanged": source_unchanged,
            },
            ensure_ascii=False,
        )
    )


def _read_artifact_file(artifact_root: Path, artifact_id: str) -> dict[str, Any]:
    path = artifact_root / f"{artifact_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_artifact_reference(payload: dict[str, Any]) -> bool:
    artifact = ArtifactRef.model_validate(payload)
    parsed = urlparse(artifact.uri)
    if parsed.scheme != "file":
        return False
    raw_path = unquote(parsed.path)
    if os.name == "nt" and len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        raw_path = raw_path[1:]
    path = Path(raw_path)
    return path.exists() and _sha256(path) == artifact.sha256


def replay(*, output_root: Path) -> None:
    output_root = output_root.resolve(strict=True)
    layout = StoreLayout.provision(
        runtime_root=output_root / "runtime",
        knowledge_source_root=output_root / "knowledge-source",
    )
    artifact_root = layout.artifact_root
    baseline_manifest = RunManifest.model_validate(
        _read_artifact_file(artifact_root, "baseline-run-manifest")
    )
    candidate_manifest = RunManifest.model_validate(
        _read_artifact_file(artifact_root, "candidate-run-manifest")
    )
    approval_ref = _artifact(
        "pinn-smoke-approval",
        REPOSITORY_ROOT
        / "openspec"
        / "changes"
        / "build-rag-multi-agent-dl-strategy-system"
        / "approval-records"
        / "2026-07-16-pinn-smoke-release-gates.md",
    )
    approval = ApprovalRecord(
        approval_id=APPROVAL_ID,
        workflow_id=WORKFLOW_ID,
        kind=ApprovalKind.EXPERIMENT,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=datetime(2026, 7, 16, tzinfo=UTC),
        scope="OpenSpec tasks 8.4-8.6; smoke only; no full run",
        evidence_refs=(approval_ref,),
    )
    backend = ForbiddenReplayBackend()
    registry = SQLiteRunRegistry(
        layout.tracking_database.parent / "launch_registry.sqlite3"
    )
    runner = ManifestFirstRunner(registry, backend)
    baseline_submission = runner.submit(baseline_manifest, approval)
    candidate_submission = runner.submit(candidate_manifest, approval)

    graph_config = {"configurable": {"thread_id": WORKFLOW_ID}}
    with SQLiteCheckpointStore(layout.checkpoint_database).open() as checkpointer:
        graph = build_phase0_graph(checkpointer)
        persisted = graph.get_state(graph_config)
        persisted_stage = persisted.values.get("stage")
    with SQLiteCheckpointStore(layout.checkpoint_database).open() as checkpointer:
        replayed_graph = build_phase0_graph(checkpointer)
        replayed_stage = replayed_graph.get_state(graph_config).values.get("stage")
    evidence_manifest = _read_artifact_file(artifact_root, "evidence-manifest")
    refs = [
        evidence_manifest["source_snapshot"],
        evidence_manifest["environment"],
        evidence_manifest["experiment_spec"],
        evidence_manifest["baseline_manifest"],
        evidence_manifest["candidate_manifest"],
        evidence_manifest["analysis"],
        evidence_manifest["candidate_validation"],
        *evidence_manifest["baseline_outputs"].values(),
        *evidence_manifest["candidate_outputs"].values(),
    ]
    provenance_valid = all(_verify_artifact_reference(item) for item in refs)
    checks = {
        "baseline_duplicate": baseline_submission.duplicate,
        "candidate_duplicate": candidate_submission.duplicate,
        "backend_not_relaunched": backend.launch_count == 0,
        "persisted_stage": persisted_stage == WorkflowStage.SMOKE_APPROVED.value,
        "replayed_stage": replayed_stage == WorkflowStage.SMOKE_APPROVED.value,
        "provenance_valid": provenance_valid,
    }
    report = {
        "workflow_id": WORKFLOW_ID,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "baseline_submission": baseline_submission.model_dump(mode="json"),
        "candidate_submission": candidate_submission.model_dump(mode="json"),
        "persisted_stage": persisted_stage,
        "replayed_stage": replayed_stage,
    }
    if not all(checks.values()):
        raise RuntimeError(f"replay checks failed: {checks}")
    artifact_store = LocalArtifactStore(artifact_root)
    replay_ref = artifact_store.put_json("replay-report", report)
    audit = AppendOnlyAuditStore(layout.audit_database)
    replay_record_id = "pinn2d-smoke-replay-verified"
    existing_record_ids = {
        record.record_id for record in audit.records_for(WORKFLOW_ID)
    }
    if replay_record_id not in existing_record_ids:
        audit.append(
            record_id=replay_record_id,
            subject_id=WORKFLOW_ID,
            category="replay_report",
            occurred_at=datetime.now(UTC),
            payload=ModelEvaluationReport(
                report_id="pinn2d-smoke-replay-evaluation",
                status=ResultStatus.VALID,
                physical_model_authority_ref=ArtifactRef.model_validate(
                    evidence_manifest["source_snapshot"]
                ),
                metric_values={"idempotent_relaunch_count": 0.0},
                metric_bases={
                    "idempotent_relaunch_count": (
                        MetricEvidenceBasis.BASELINE_RUN
                    )
                },
                diagnostic_refs=(replay_ref,),
                checks=checks,
            ),
        )
    print(json.dumps({"replay_report": replay_ref.uri, "status": "PASS"}))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--case-root", type=Path, required=True)
    execute_parser.add_argument("--training-python", type=Path, required=True)
    execute_parser.add_argument("--output-root", type=Path, required=True)
    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "execute":
        execute(
            case_root=args.case_root,
            training_python=args.training_python,
            output_root=args.output_root,
        )
    else:
        replay(output_root=args.output_root)


if __name__ == "__main__":
    main()

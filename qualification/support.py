"""Shared, repository-independent support for governed qualification runs."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from pinn_strategy_system.assurance import EventMonitor
from pinn_strategy_system.contracts import (
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactCollectionReport,
    ArtifactCollectionSpec,
    ArtifactCollectionStatus,
    ArtifactRef,
    BackendRunPhase,
    BackendRunRef,
    BackendRunStatus,
    ExecutionRequest,
    MonitoringPolicy,
    PreparedRun,
    RunCancellationRequest,
    RunEvent,
    RunEventType,
    RunManifest,
)
from pinn_strategy_system.execution import (
    ApprovedProcessIdentity,
    ApprovedProcessSampler,
    ExecutionBackend,
    LocalProcessBackendConfig,
    LocalProcessRunnerBackend,
    ManifestFirstRunner,
    ProcessUnavailableError,
)
from pinn_strategy_system.storage import AppendOnlyAuditStore


def load_approval(
    path: Path,
    *,
    workflow_id: str,
    kind: ApprovalKind,
    scope: str,
) -> ApprovalRecord:
    """Load one explicit, case-scoped approval supplied by the operator."""
    payload = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    record = ApprovalRecord.model_validate(payload)
    if (
        record.workflow_id != workflow_id
        or record.kind is not kind
        or record.decision is not ApprovalDecision.APPROVED
        or record.scope != scope
    ):
        raise ValueError(
            f"approval does not authorize {kind.value} for workflow {workflow_id}"
        )
    return record


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
        (name, os.environ[name]) for name in allowed_names if name in os.environ
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
    """Fail if an idempotent evidence replay attempts a new launch."""

    def __init__(self) -> None:
        self.launch_count = 0

    def prepare(self, request: ExecutionRequest) -> PreparedRun:
        self.launch_count += 1
        raise AssertionError(f"replay attempted to prepare {request.manifest.run_id}")

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
    expected_outputs: tuple[str, ...],
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
            sampler = ApprovedProcessSampler(
                (
                    ApprovedProcessIdentity(
                        run_id=manifest.run_id,
                        pid=status.process_id,
                        expected_create_time=status.process_create_time,
                        approval_id=approval.approval_id,
                    ),
                )
            )
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
                        event_id=f"{manifest.run_id}-resource-{sample_index}",
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
        if report is None or report.status is not ArtifactCollectionStatus.COMPLETE:
            raise RuntimeError("local backend artifact collection was not complete")
        artifact_directory = collection_directory

    artifacts: dict[str, ArtifactRef] = {}
    for relative in expected_outputs:
        path = artifact_directory / Path(relative)
        if path.exists():
            artifact_id = f"{manifest.run_id}-{relative.replace('/', '_')}"
            artifacts[relative] = _artifact(artifact_id, path)

    if submission.prepared_run is None:
        raise RuntimeError("local run has no prepared-run evidence")
    run_directory = Path(submission.prepared_run.staging_root)
    combined_log = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (run_directory / "stdout.log", run_directory / "stderr.log")
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

    checkpoint = next(
        (
            artifact
            for name, artifact in artifacts.items()
            if name.endswith((".pt", ".pth"))
        ),
        None,
    )
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
            payload={"exit_code": exit_code, "backend_phase": status.phase.value},
            artifacts=tuple(artifacts.values()),
        )
    )

    required_ids = tuple(
        f"{manifest.run_id}-{name.replace('/', '_')}" for name in expected_outputs
    )
    monitoring = EventMonitor().evaluate(
        report_id=f"{manifest.run_id}-monitoring",
        run_id=manifest.run_id,
        events=tuple(events),
        policy=MonitoringPolicy(
            policy_id="qualification-process-policy",
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

"""Durable local process backend with explicit environment and artifact IO."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

from pinn_strategy_system.contracts import (
    ArtifactCollectionReport,
    ArtifactCollectionSpec,
    ArtifactCollectionStatus,
    ArtifactRef,
    BackendRunPhase,
    BackendRunRef,
    BackendRunStatus,
    ExecutionRequest,
    LogCursor,
    PreparedRun,
    RunCancellationRequest,
    RunManifest,
)


@dataclass(frozen=True)
class LocalProcessBackendConfig:
    run_root: Path
    launcher_interpreter: Path
    environment: tuple[tuple[str, str], ...]
    environment_allowlist: tuple[str, ...]
    heartbeat_interval_seconds: float = 0.5
    heartbeat_stale_after_seconds: float = 5.0
    cancellation_timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        root = self.run_root
        interpreter = self.launcher_interpreter
        if not root.is_absolute() or not root.exists() or not root.is_dir():
            raise ValueError(
                "local backend run_root must be an existing absolute directory"
            )
        if (
            not interpreter.is_absolute()
            or not interpreter.exists()
            or not interpreter.is_file()
        ):
            raise ValueError(
                "local backend launcher_interpreter must be an existing absolute file"
            )
        names = tuple(name.casefold() for name, _ in self.environment)
        if len(names) != len(set(names)):
            raise ValueError("local backend environment names must be unique")
        allowed = tuple(name.casefold() for name in self.environment_allowlist)
        if len(allowed) != len(set(allowed)):
            raise ValueError("local backend allowlist names must be unique")
        if any(name not in allowed for name in names):
            raise ValueError(
                "local backend environment contains a non-allowlisted name"
            )
        if self.heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat interval must be positive")
        if self.heartbeat_stale_after_seconds <= self.heartbeat_interval_seconds:
            raise ValueError("stale heartbeat threshold must exceed heartbeat interval")
        if self.cancellation_timeout_seconds <= 0:
            raise ValueError("cancellation timeout must be positive")

    def environment_dict(self) -> dict[str, str]:
        return dict(self.environment)


@dataclass(frozen=True)
class _RunPaths:
    root: Path
    request: Path
    command_manifest: Path
    environment_manifest: Path
    launch_payload: Path
    launcher_identity: Path
    process_identity: Path
    status_events: Path
    heartbeats: Path
    stdout: Path
    stderr: Path


class LocalProcessRunnerBackend:
    def __init__(self, config: LocalProcessBackendConfig) -> None:
        self._config = config
        self._local_launcher_handles: dict[str, subprocess.Popen] = {}

    def prepare(self, request: ExecutionRequest) -> PreparedRun:
        manifest = request.manifest
        _validate_local_manifest(manifest)
        _validate_command_has_no_embedded_secret(manifest.command)
        paths = self._paths(manifest.run_id)
        paths.root.mkdir(parents=False, exist_ok=True)
        if not paths.root.is_dir():
            raise ValueError("local run root must be a directory")
        paths.status_events.mkdir(exist_ok=True)
        paths.heartbeats.mkdir(exist_ok=True)
        request_payload = request.model_dump(mode="json")
        command_payload = {
            "command": list(manifest.command),
            "interpreter": manifest.interpreter,
            "working_directory": manifest.working_directory,
            "output_root": manifest.output_root,
            "expected_artifacts": list(manifest.expected_artifacts),
            "config_ref": manifest.config_ref.model_dump(mode="json"),
        }
        environment_payload = {
            "environment_name": manifest.environment_name,
            "provided_names": sorted(name for name, _ in self._config.environment),
            "allowlisted_names": sorted(self._config.environment_allowlist),
            "values_persisted": False,
        }
        launch_payload = {
            "run_id": manifest.run_id,
            "command": list(manifest.command),
            "working_directory": manifest.working_directory,
            "output_root": manifest.output_root,
            "expected_artifacts": list(manifest.expected_artifacts),
            "heartbeat_interval_seconds": self._config.heartbeat_interval_seconds,
        }
        _write_or_verify(paths.request, request_payload)
        _write_or_verify(paths.command_manifest, command_payload)
        _write_or_verify(paths.environment_manifest, environment_payload)
        _write_or_verify(paths.launch_payload, launch_payload)
        backend_ref = BackendRunRef(
            backend_id="local-process-v1",
            run_id=manifest.run_id,
            idempotency_key=manifest.idempotency_key,
            reference=f"local-process://{manifest.run_id}",
        )
        return PreparedRun(
            request=request,
            backend_ref=backend_ref,
            staging_root=str(paths.root),
            prepared_at=datetime.now(UTC),
            launch_metadata={
                "run_directory": str(paths.root),
                "request_sha256": _sha256(paths.request),
                "environment_names": environment_payload["provided_names"],
            },
        )

    def launch(self, prepared_run: PreparedRun) -> BackendRunRef:
        paths = self._paths(prepared_run.backend_ref.run_id)
        _validate_prepared_root(prepared_run, paths.root)
        if paths.launcher_identity.exists():
            raise FileExistsError("local run already has a launcher identity")
        worker = Path(__file__).with_name("_local_worker.py").resolve(strict=True)
        command = (
            str(self._config.launcher_interpreter),
            str(worker),
            "--payload",
            str(paths.launch_payload),
            "--run-root",
            str(paths.root),
        )
        process = subprocess.Popen(
            command,
            cwd=paths.root,
            env=self._config.environment_dict(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
            start_new_session=os.name != "nt",
        )
        identity = {
            "pid": process.pid,
            "create_time": psutil.Process(process.pid).create_time(),
            "recorded_at": _now(),
        }
        self._local_launcher_handles[prepared_run.backend_ref.run_id] = process
        _write_json_exclusive(paths.launcher_identity, identity)
        return prepared_run.backend_ref

    def reconcile(self, backend_ref: BackendRunRef) -> BackendRunStatus:
        paths = self._paths(backend_ref.run_id)
        request = ExecutionRequest.model_validate(
            json.loads(paths.request.read_text(encoding="utf-8"))
        )
        _validate_backend_ref(request.manifest, backend_ref)
        event = _latest_json(paths.status_events)
        identity = _read_identity(paths.process_identity)
        if identity is None:
            identity = _read_identity(paths.launcher_identity)
        process_matches = _identity_is_live(identity)
        heartbeat_at = _latest_event_time(paths.heartbeats)
        produced = _produced_artifacts(request.manifest)
        missing = tuple(
            name
            for name in request.manifest.expected_artifacts
            if name not in produced
        )
        observed_at = datetime.now(UTC)
        phase, detail = _reconciled_phase(
            event,
            process_matches,
            missing,
            heartbeat_at=heartbeat_at,
            heartbeat_stale_after_seconds=(
                self._config.heartbeat_stale_after_seconds
            ),
            observed_at=observed_at,
        )
        checks = {
            "status_event_valid": event is not None,
            "process_identity_recorded": identity is not None,
            "required_artifacts_present": not missing,
        }
        exit_code = None if event is None else event.get("exit_code")
        self._reap_local_launcher(backend_ref.run_id)
        return BackendRunStatus(
            backend_ref=backend_ref,
            phase=phase,
            observed_at=observed_at,
            process_id=None if identity is None else int(identity["pid"]),
            process_create_time=(
                None if identity is None else float(identity["create_time"])
            ),
            exit_code=exit_code if isinstance(exit_code, int) else None,
            heartbeat_at=heartbeat_at,
            log_cursor=LogCursor(
                stdout_offset=_size_or_zero(paths.stdout),
                stderr_offset=_size_or_zero(paths.stderr),
                observed_at=observed_at,
            ),
            produced_artifacts=produced,
            checks=checks,
            detail=detail,
        )

    def cancel(
        self,
        backend_ref: BackendRunRef,
        request: RunCancellationRequest,
    ) -> BackendRunStatus:
        paths = self._paths(backend_ref.run_id)
        _write_json_exclusive(
            paths.root / "cancellation-approval.json",
            request.model_dump(mode="json"),
        )
        identities = tuple(
            identity
            for identity in (
                _read_identity(paths.process_identity),
                _read_identity(paths.launcher_identity),
            )
            if identity is not None
        )
        for identity in identities:
            _terminate_matching_tree(
                identity,
                timeout_seconds=self._config.cancellation_timeout_seconds,
            )
        still_live = any(_identity_is_live(identity) for identity in identities)
        self._reap_local_launcher(backend_ref.run_id, wait=True)
        stop_confirmed = bool(identities) and not still_live
        phase = (
            BackendRunPhase.CANCELLED
            if stop_confirmed
            else BackendRunPhase.RUNNING_UNKNOWN
        )
        _write_event(
            paths.status_events,
            "cancelled" if stop_confirmed else "cancel-uncertain",
            {
                "phase": phase.value,
                "observed_at": _now(),
                "exit_code": None,
                "detail": request.reason,
            },
        )
        return BackendRunStatus(
            backend_ref=backend_ref,
            phase=phase,
            observed_at=datetime.now(UTC),
            checks={
                "approval_recorded": True,
                "process_identity_recorded": bool(identities),
                "process_tree_stopped": stop_confirmed,
            },
            detail=request.reason,
        )

    def collect(
        self,
        backend_ref: BackendRunRef,
        spec: ArtifactCollectionSpec,
    ) -> ArtifactCollectionReport:
        paths = self._paths(backend_ref.run_id)
        request = ExecutionRequest.model_validate(
            json.loads(paths.request.read_text(encoding="utf-8"))
        )
        _validate_backend_ref(request.manifest, backend_ref)
        destination = Path(spec.destination_root)
        if not destination.is_absolute():
            raise ValueError("artifact destination must be absolute")
        if not destination.parent.exists():
            raise ValueError("artifact destination parent must already exist")
        output_root = Path(request.manifest.output_root).resolve(strict=True)
        entries, missing = _source_entries(output_root, spec.required_artifacts)
        source_manifest_path = paths.root / "collection-source-manifest.json"
        _write_or_verify(
            source_manifest_path,
            {
                "run_id": backend_ref.run_id,
                "output_root": str(output_root),
                "entries": entries,
                "missing": list(missing),
            },
        )
        source_manifest_ref = _artifact_ref(
            f"{backend_ref.run_id}-collection-source-manifest",
            source_manifest_path,
        )
        if missing:
            return ArtifactCollectionReport(
                run_id=backend_ref.run_id,
                status=ArtifactCollectionStatus.PARTIAL,
                source_manifest_ref=source_manifest_ref,
                findings=(f"missing required artifacts: {', '.join(missing)}",),
            )
        collection_marker_payload = {
            "run_id": backend_ref.run_id,
            "backend_ref": backend_ref.model_dump(mode="json"),
            "source_manifest_sha256": source_manifest_ref.sha256,
            "required_artifacts": list(spec.required_artifacts),
        }
        if destination.exists():
            if not destination.is_dir():
                raise FileExistsError(
                    "artifact destination exists and is not a directory"
                )
            marker = destination / "collection-request.json"
            if not marker.is_file():
                raise FileExistsError(
                    "artifact destination exists without a governed collection marker"
                )
            _write_or_verify(marker, collection_marker_payload)
        else:
            destination.mkdir(parents=False, exist_ok=False)
            marker = destination / "collection-request.json"
            _write_json_exclusive(marker, collection_marker_payload)
        copied_refs: list[ArtifactRef] = []
        try:
            for entry in entries:
                relative = Path(entry["relative_path"])
                source = output_root / relative
                target = destination / relative
                target.resolve(strict=False).relative_to(
                    destination.resolve(strict=True)
                )
                if target.exists():
                    if not target.is_file() or _sha256(target) != entry["sha256"]:
                        raise FileExistsError(
                            f"existing destination artifact differs: {relative}"
                        )
                    copied_refs.append(
                        _artifact_ref(
                            _artifact_id(
                                backend_ref.run_id,
                                entry["relative_path"],
                            ),
                            target,
                        )
                    )
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                if (
                    target.stat().st_size != entry["size_bytes"]
                    or _sha256(target) != entry["sha256"]
                ):
                    raise OSError(f"copied artifact verification failed: {relative}")
                copied_refs.append(
                    _artifact_ref(
                        _artifact_id(backend_ref.run_id, entry["relative_path"]),
                        target,
                    )
                )
            destination_manifest_path = destination / "artifact-manifest.json"
            _write_or_verify(
                destination_manifest_path,
                {
                    "run_id": backend_ref.run_id,
                    "source_manifest_sha256": source_manifest_ref.sha256,
                    "entries": [
                        reference.model_dump(mode="json")
                        for reference in copied_refs
                    ],
                },
            )
        except Exception as error:
            return ArtifactCollectionReport(
                run_id=backend_ref.run_id,
                status=ArtifactCollectionStatus.PARTIAL,
                artifact_refs=tuple(copied_refs),
                source_manifest_ref=source_manifest_ref,
                findings=(f"collection interrupted: {type(error).__name__}",),
            )
        destination_manifest_ref = _artifact_ref(
            f"{backend_ref.run_id}-collection-destination-manifest",
            destination_manifest_path,
        )
        return ArtifactCollectionReport(
            run_id=backend_ref.run_id,
            status=ArtifactCollectionStatus.COMPLETE,
            artifact_refs=tuple(copied_refs),
            source_manifest_ref=source_manifest_ref,
            destination_manifest_ref=destination_manifest_ref,
        )

    def _paths(self, run_id: str) -> _RunPaths:
        if Path(run_id).name != run_id:
            raise ValueError("run_id must be a single safe path segment")
        root = (self._config.run_root / run_id).resolve(strict=False)
        root.relative_to(self._config.run_root.resolve(strict=True))
        return _RunPaths(
            root=root,
            request=root / "execution-request.json",
            command_manifest=root / "command-manifest.json",
            environment_manifest=root / "environment-manifest.json",
            launch_payload=root / "launch-payload.json",
            launcher_identity=root / "launcher-identity.json",
            process_identity=root / "process-identity.json",
            status_events=root / "status-events",
            heartbeats=root / "heartbeats",
            stdout=root / "stdout.log",
            stderr=root / "stderr.log",
        )

    def _reap_local_launcher(self, run_id: str, *, wait: bool = False) -> None:
        process = self._local_launcher_handles.get(run_id)
        if process is None:
            return
        if wait:
            try:
                process.wait(timeout=self._config.cancellation_timeout_seconds)
            except subprocess.TimeoutExpired:
                return
        elif process.poll() is None:
            return
        self._local_launcher_handles.pop(run_id, None)


def _validate_local_manifest(manifest: RunManifest) -> None:
    working_directory = Path(manifest.working_directory)
    interpreter = Path(manifest.interpreter)
    output_root = Path(manifest.output_root)
    if not working_directory.is_absolute() or not working_directory.is_dir():
        raise ValueError(
            "local working_directory must be an existing absolute directory"
        )
    if not interpreter.is_absolute() or not interpreter.is_file():
        raise ValueError("local interpreter must be an existing absolute file")
    command_executable = Path(manifest.command[0])
    if not command_executable.is_absolute() or not command_executable.is_file():
        raise ValueError(
            "local command must start with an existing absolute executable"
        )
    if os.path.normcase(str(command_executable.resolve())) != os.path.normcase(
        str(interpreter.resolve())
    ):
        raise ValueError("local command executable must match manifest interpreter")
    if not output_root.is_absolute():
        raise ValueError("local output_root must be absolute")
    for relative in manifest.expected_artifacts:
        _safe_relative_path(relative)


def _validate_command_has_no_embedded_secret(command: tuple[str, ...]) -> None:
    forbidden_flags = (
        "--password",
        "--passwd",
        "--token",
        "--api-key",
        "--apikey",
        "--secret",
    )
    for argument in command:
        normalized = argument.casefold()
        if normalized in forbidden_flags or any(
            normalized.startswith(f"{flag}=") for flag in forbidden_flags
        ):
            raise ValueError("command contains a forbidden secret-bearing argument")
        if re.search(r"://[^/@:\s]+:[^/@\s]+@", argument):
            raise ValueError("command contains credentials embedded in a URI")


def _validate_prepared_root(prepared_run: PreparedRun, expected_root: Path) -> None:
    if Path(prepared_run.staging_root).resolve(strict=True) != expected_root:
        raise ValueError("prepared staging_root does not match backend run root")


def _validate_backend_ref(
    manifest: RunManifest,
    backend_ref: BackendRunRef,
) -> None:
    if backend_ref.backend_id != "local-process-v1":
        raise ValueError("backend reference does not belong to local-process-v1")
    if backend_ref.run_id != manifest.run_id:
        raise ValueError("backend reference run_id mismatch")
    if backend_ref.idempotency_key != manifest.idempotency_key:
        raise ValueError("backend reference idempotency_key mismatch")


def _reconciled_phase(
    event: dict[str, Any] | None,
    process_matches: bool,
    missing_artifacts: tuple[str, ...],
    *,
    heartbeat_at: datetime | None,
    heartbeat_stale_after_seconds: float,
    observed_at: datetime,
) -> tuple[BackendRunPhase, str | None]:
    if event is None:
        return BackendRunPhase.RUNNING_UNKNOWN, "no durable status event"
    event_phase = BackendRunPhase(event["phase"])
    if event_phase is BackendRunPhase.COMPLETED and missing_artifacts:
        return (
            BackendRunPhase.FAILED,
            f"completed process is missing artifacts: {', '.join(missing_artifacts)}",
        )
    terminal = (
        BackendRunPhase.COMPLETED,
        BackendRunPhase.FAILED,
        BackendRunPhase.CANCELLED,
    )
    if event_phase in terminal:
        return event_phase, event.get("detail")
    if process_matches:
        signal_at = heartbeat_at or datetime.fromisoformat(event["observed_at"])
        if (observed_at - signal_at).total_seconds() > heartbeat_stale_after_seconds:
            return BackendRunPhase.RUNNING_UNKNOWN, "heartbeat is stale"
        if event_phase is BackendRunPhase.PREPARED:
            return BackendRunPhase.RUNNING, "launcher is live; child startup is pending"
        return event_phase, event.get("detail")
    return BackendRunPhase.RUNNING_UNKNOWN, "recorded process identity is not live"


def _produced_artifacts(manifest: RunManifest) -> tuple[str, ...]:
    output_root = Path(manifest.output_root)
    return tuple(
        relative
        for relative in manifest.expected_artifacts
        if (output_root / _safe_relative_path(relative)).is_file()
    )


def _source_entries(
    output_root: Path,
    required: tuple[str, ...],
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    entries: list[dict[str, Any]] = []
    missing: list[str] = []
    for name in required:
        relative = _safe_relative_path(name)
        path = (output_root / relative).resolve(strict=False)
        path.relative_to(output_root)
        if not path.is_file():
            missing.append(name)
            continue
        entries.append(
            {
                "relative_path": name,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return entries, tuple(missing)


def _safe_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        raise ValueError("artifact path must be a safe relative path")
    return path


def _read_identity(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("pid"), int):
        raise ValueError("process identity is missing pid")
    if not isinstance(payload.get("create_time"), (int, float)):
        raise ValueError("process identity is missing create_time")
    return payload


def _identity_is_live(identity: dict[str, Any] | None) -> bool:
    if identity is None:
        return False
    try:
        process = psutil.Process(int(identity["pid"]))
        return (
            process.is_running()
            and process.status() != psutil.STATUS_ZOMBIE
            and abs(process.create_time() - float(identity["create_time"])) < 0.01
        )
    except (psutil.Error, OSError, ValueError):
        return False


def _terminate_matching_tree(
    identity: dict[str, Any],
    *,
    timeout_seconds: float,
) -> None:
    if not _identity_is_live(identity):
        return
    process = psutil.Process(int(identity["pid"]))
    targets = tuple(process.children(recursive=True)) + (process,)
    for target in targets:
        try:
            target.terminate()
        except psutil.Error:
            continue
    _, alive = psutil.wait_procs(targets, timeout=timeout_seconds)
    for target in alive:
        try:
            target.kill()
        except psutil.Error:
            continue
    if alive:
        psutil.wait_procs(alive, timeout=timeout_seconds)


def _latest_json(root: Path) -> dict[str, Any] | None:
    candidates = tuple(sorted(root.glob("*.json")))
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def _latest_event_time(root: Path) -> datetime | None:
    payload = _latest_json(root)
    if payload is None:
        return None
    return datetime.fromisoformat(payload["observed_at"])


def _size_or_zero(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _write_or_verify(path: Path, payload: dict[str, Any]) -> None:
    encoded = _canonical_json(payload)
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"governed manifest already differs: {path.name}")
        return
    try:
        _write_json_exclusive(path, payload)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(
                f"governed manifest already differs: {path.name}"
            ) from None


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(_canonical_json(payload))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_event(root: Path, label: str, payload: dict[str, Any]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{time.time_ns():020d}-{label}-{uuid.uuid4().hex}.json"
    _write_json_exclusive(path, payload)
    return path


def _canonical_json(payload: dict[str, Any]) -> str:
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_ref(artifact_id: str, path: Path) -> ArtifactRef:
    resolved = path.resolve(strict=True)
    return ArtifactRef(
        artifact_id=artifact_id,
        uri=resolved.as_uri(),
        sha256=_sha256(resolved),
        size_bytes=resolved.stat().st_size,
    )


def _artifact_id(run_id: str, relative_path: str) -> str:
    suffix = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:16]
    return f"{run_id}-artifact-{suffix}"


def _now() -> str:
    return datetime.now(UTC).isoformat()

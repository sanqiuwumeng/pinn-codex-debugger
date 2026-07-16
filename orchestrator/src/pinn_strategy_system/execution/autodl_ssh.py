"""AutoDL SSH execution backend with durable remote reconciliation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tarfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse

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
    SshConnectionProfile,
)

from .ssh_transport import AutoDlTransport, SshTransportError


@dataclass(frozen=True)
class AutoDlSshBackendConfig:
    connection_profile: SshConnectionProfile
    remote_root: PurePosixPath
    local_control_root: Path
    remote_environment: tuple[tuple[str, str], ...]
    environment_allowlist: tuple[str, ...]
    heartbeat_interval_seconds: float = 1.0
    heartbeat_stale_after_seconds: float = 15.0

    def __post_init__(self) -> None:
        _validate_remote_path(self.remote_root)
        if not self.local_control_root.is_absolute():
            raise ValueError("AutoDL local control root must be absolute")
        if not self.local_control_root.is_dir():
            raise ValueError("AutoDL local control root must exist")
        names = tuple(name.casefold() for name, _ in self.remote_environment)
        allowed = tuple(name.casefold() for name in self.environment_allowlist)
        if len(names) != len(set(names)) or len(allowed) != len(set(allowed)):
            raise ValueError("AutoDL environment names must be unique")
        if any(name not in allowed for name in names):
            raise ValueError("AutoDL environment contains a non-allowlisted name")
        if any(_credential_like_name(name) for name in names):
            raise ValueError("AutoDL environment contains a credential-like name")
        if self.heartbeat_interval_seconds <= 0:
            raise ValueError("AutoDL heartbeat interval must be positive")
        if self.heartbeat_stale_after_seconds <= self.heartbeat_interval_seconds:
            raise ValueError("AutoDL stale threshold must exceed heartbeat interval")


@dataclass(frozen=True)
class _AutoDlPaths:
    local_root: Path
    local_request: Path
    local_profile: Path
    local_environment: Path
    local_layout: Path
    local_prepare_payload: Path
    local_transfers: Path
    remote_run_root: PurePosixPath
    remote_workspace: PurePosixPath
    remote_worker: PurePosixPath
    remote_staging_archive: PurePosixPath
    remote_prepare_payload: PurePosixPath


class AutoDlSshRunnerBackend:
    def __init__(
        self,
        config: AutoDlSshBackendConfig,
        transport: AutoDlTransport,
    ) -> None:
        self._config = config
        self._transport = transport

    def prepare(self, request: ExecutionRequest) -> PreparedRun:
        manifest = request.manifest
        archive = _validate_remote_manifest(
            manifest,
            remote_root=self._config.remote_root,
        )
        paths = self._paths(manifest.run_id, archive_sha256=manifest.config_ref.sha256)
        paths.local_root.mkdir(parents=False, exist_ok=True)
        if not paths.local_root.is_dir():
            raise ValueError("AutoDL local run control path must be a directory")
        worker = Path(__file__).with_name("_autodl_worker.py").resolve(strict=True)
        worker_sha = _sha256(worker)
        remote_worker = (
            self._config.remote_root
            / ".backend"
            / "workers"
            / worker_sha
            / "_autodl_worker.py"
        )
        if remote_worker != paths.remote_worker:
            raise RuntimeError("AutoDL worker layout mismatch")
        prepare_payload = {
            "run_id": manifest.run_id,
            "request_id": request.request_id,
            "connection_profile": self._config.connection_profile.model_dump(
                mode="json"
            ),
            "approval": request.approval.model_dump(mode="json"),
            "remote_root": str(self._config.remote_root),
            "run_root": str(paths.remote_run_root),
            "staging_archive": str(paths.remote_staging_archive),
            "staging_archive_sha256": manifest.config_ref.sha256,
            "interpreter": manifest.interpreter,
            "working_directory": manifest.working_directory,
            "command": list(manifest.command),
            "output_root": manifest.output_root,
            "expected_artifacts": list(manifest.expected_artifacts),
            "environment": [list(item) for item in self._config.remote_environment],
            "heartbeat_interval_seconds": self._config.heartbeat_interval_seconds,
            "heartbeat_stale_after_seconds": (
                self._config.heartbeat_stale_after_seconds
            ),
        }
        _write_or_verify(
            paths.local_request,
            request.model_dump(mode="json"),
        )
        _write_or_verify(
            paths.local_profile,
            self._config.connection_profile.model_dump(mode="json"),
        )
        _write_or_verify(
            paths.local_environment,
            {
                "provided_names": sorted(
                    name for name, _ in self._config.remote_environment
                ),
                "allowlisted_names": sorted(self._config.environment_allowlist),
                "connection_values_persisted": False,
                "credential_like_names_allowed": False,
            },
        )
        _write_or_verify(
            paths.local_layout,
            {
                "remote_root": str(self._config.remote_root),
                "remote_run_root": str(paths.remote_run_root),
                "remote_worker": str(paths.remote_worker),
                "remote_staging_archive": str(paths.remote_staging_archive),
                "remote_prepare_payload": str(paths.remote_prepare_payload),
            },
        )
        _write_or_verify(paths.local_prepare_payload, prepare_payload)
        self._transport.ensure_directory(self._config.remote_root)
        self._transport.install_content(worker, paths.remote_worker, worker_sha)
        self._transport.install_content(
            archive,
            paths.remote_staging_archive,
            manifest.config_ref.sha256,
        )
        self._transport.install_content(
            paths.local_prepare_payload,
            paths.remote_prepare_payload,
            _sha256(paths.local_prepare_payload),
        )
        response = self._transport.invoke(
            paths.remote_worker,
            ("prepare", "--payload", str(paths.remote_prepare_payload)),
        )
        if response.get("status") != "prepared":
            raise RuntimeError("AutoDL remote preparation did not complete")
        if response.get("staging_archive_sha256") != manifest.config_ref.sha256:
            raise RuntimeError("AutoDL staging archive was not verified")
        backend_ref = BackendRunRef(
            backend_id="autodl-ssh-v1",
            run_id=manifest.run_id,
            idempotency_key=manifest.idempotency_key,
            reference=(
                f"autodl-ssh://{self._config.connection_profile.profile_id}/"
                f"{manifest.run_id}"
            ),
        )
        return PreparedRun(
            request=request,
            backend_ref=backend_ref,
            staging_root=str(paths.local_root),
            prepared_at=datetime.now(UTC),
            launch_metadata={
                "profile_id": self._config.connection_profile.profile_id,
                "remote_run_root": str(paths.remote_run_root),
                "staging_archive_sha256": manifest.config_ref.sha256,
                "worker_sha256": worker_sha,
            },
        )

    def launch(self, prepared_run: PreparedRun) -> BackendRunRef:
        manifest = prepared_run.request.manifest
        paths = self._paths(manifest.run_id, archive_sha256=manifest.config_ref.sha256)
        if Path(prepared_run.staging_root).resolve(strict=True) != paths.local_root:
            raise ValueError("AutoDL prepared staging root mismatch")
        response = self._transport.invoke(
            paths.remote_worker,
            ("launch", "--run-root", str(paths.remote_run_root)),
        )
        if response.get("status") not in ("launched", "reused"):
            raise RuntimeError("AutoDL durable launcher returned an invalid status")
        return prepared_run.backend_ref

    def reconcile(self, backend_ref: BackendRunRef) -> BackendRunStatus:
        manifest = self._manifest_for(backend_ref)
        paths = self._paths(manifest.run_id, archive_sha256=manifest.config_ref.sha256)
        try:
            response = self._transport.invoke(
                paths.remote_worker,
                ("status", "--run-root", str(paths.remote_run_root)),
            )
        except SshTransportError as error:
            return BackendRunStatus(
                backend_ref=backend_ref,
                phase=BackendRunPhase.RUNNING_UNKNOWN,
                observed_at=datetime.now(UTC),
                checks={"transport_reachable": False},
                detail=str(error),
            )
        return _backend_status(backend_ref, response)

    def cancel(
        self,
        backend_ref: BackendRunRef,
        request: RunCancellationRequest,
    ) -> BackendRunStatus:
        manifest = self._manifest_for(backend_ref)
        if request.run_id != manifest.run_id:
            raise ValueError("AutoDL cancellation run_id mismatch")
        paths = self._paths(manifest.run_id, archive_sha256=manifest.config_ref.sha256)
        local_request = paths.local_root / "cancellation-approval.json"
        payload = request.model_dump(mode="json")
        _write_or_verify(local_request, payload)
        remote_request = paths.remote_run_root / "cancellation-approval.json"
        try:
            self._transport.install_content(
                local_request,
                remote_request,
                _sha256(local_request),
            )
            response = self._transport.invoke(
                paths.remote_worker,
                (
                    "cancel",
                    "--run-root",
                    str(paths.remote_run_root),
                    "--payload",
                    str(remote_request),
                ),
            )
        except SshTransportError as error:
            return BackendRunStatus(
                backend_ref=backend_ref,
                phase=BackendRunPhase.RUNNING_UNKNOWN,
                observed_at=datetime.now(UTC),
                checks={
                    "approval_recorded_locally": True,
                    "transport_reachable": False,
                },
                detail=str(error),
            )
        return _backend_status(backend_ref, response)

    def collect(
        self,
        backend_ref: BackendRunRef,
        spec: ArtifactCollectionSpec,
    ) -> ArtifactCollectionReport:
        manifest = self._manifest_for(backend_ref)
        if spec.run_id != manifest.run_id or spec.backend_ref != backend_ref:
            raise ValueError("AutoDL collection spec does not match backend run")
        if spec.required_artifacts != manifest.expected_artifacts:
            raise ValueError("AutoDL collection must request all declared artifacts")
        paths = self._paths(manifest.run_id, archive_sha256=manifest.config_ref.sha256)
        local_request = paths.local_root / "collection-request.json"
        request_payload = spec.model_dump(mode="json")
        _write_or_verify(local_request, request_payload)
        remote_request = paths.remote_run_root / "collection-request.json"
        try:
            self._transport.install_content(
                local_request,
                remote_request,
                _sha256(local_request),
            )
            response = self._transport.invoke(
                paths.remote_worker,
                (
                    "collect",
                    "--run-root",
                    str(paths.remote_run_root),
                    "--payload",
                    str(remote_request),
                ),
            )
        except SshTransportError as error:
            return ArtifactCollectionReport(
                run_id=manifest.run_id,
                status=ArtifactCollectionStatus.PARTIAL,
                findings=(f"remote collection unavailable: {type(error).__name__}",),
            )
        if response.get("status") != "COMPLETE":
            missing = tuple(response.get("missing_artifacts", ()))
            return ArtifactCollectionReport(
                run_id=manifest.run_id,
                status=ArtifactCollectionStatus.PARTIAL,
                findings=(
                    "remote required artifacts are incomplete"
                    + (f": {', '.join(missing)}" if missing else ""),
                ),
            )
        archive_sha = _require_sha256(response.get("archive_sha256"))
        destination = Path(spec.destination_root)
        if not destination.is_absolute() or not destination.parent.is_dir():
            raise ValueError(
                "artifact destination parent must be absolute and existing"
            )
        existing = _existing_complete_collection(
            destination,
            run_id=manifest.run_id,
            archive_sha256=archive_sha,
        )
        if existing is not None:
            return existing
        paths.local_transfers.mkdir(exist_ok=True)
        transfer_id = uuid.uuid4().hex
        quarantine_archive = (
            paths.local_transfers / f"{transfer_id}.partial.tar"
        )
        remote_archive = _confined_remote(
            PurePosixPath(response["archive_path"]),
            paths.remote_run_root,
        )
        try:
            self._transport.download(remote_archive, quarantine_archive)
        except SshTransportError as error:
            return ArtifactCollectionReport(
                run_id=manifest.run_id,
                status=ArtifactCollectionStatus.PARTIAL,
                findings=(
                    f"partial transfer quarantined: {type(error).__name__}",
                ),
            )
        if _sha256(quarantine_archive) != archive_sha:
            return ArtifactCollectionReport(
                run_id=manifest.run_id,
                status=ArtifactCollectionStatus.PARTIAL,
                findings=("downloaded archive SHA-256 mismatch",),
            )
        extraction_root = paths.local_transfers / f"{transfer_id}.partial"
        extraction_root.mkdir(exist_ok=False)
        try:
            _extract_collection_archive(
                quarantine_archive,
                extraction_root,
                tuple(response["entries"]),
            )
            return _promote_collection(
                extraction_root,
                destination,
                run_id=manifest.run_id,
                archive_sha256=archive_sha,
                remote_source_sha256=_require_sha256(
                    response.get("source_manifest_sha256")
                ),
                entries=tuple(response["entries"]),
            )
        except Exception as error:
            return ArtifactCollectionReport(
                run_id=manifest.run_id,
                status=ArtifactCollectionStatus.PARTIAL,
                findings=(
                    f"transfer verification quarantined: {type(error).__name__}",
                ),
            )

    def _manifest_for(self, backend_ref: BackendRunRef) -> RunManifest:
        if backend_ref.backend_id != "autodl-ssh-v1":
            raise ValueError("backend reference does not belong to AutoDL SSH")
        local_root = self._safe_local_run_root(backend_ref.run_id)
        request = ExecutionRequest.model_validate(
            _read_json(local_root / "execution-request.json")
        )
        manifest = request.manifest
        if manifest.idempotency_key != backend_ref.idempotency_key:
            raise ValueError("AutoDL backend idempotency key mismatch")
        expected_reference = (
            f"autodl-ssh://{self._config.connection_profile.profile_id}/"
            f"{manifest.run_id}"
        )
        if backend_ref.reference != expected_reference:
            raise ValueError("AutoDL backend reference mismatch")
        return manifest

    def _paths(self, run_id: str, *, archive_sha256: str) -> _AutoDlPaths:
        local_root = self._safe_local_run_root(run_id)
        worker = Path(__file__).with_name("_autodl_worker.py").resolve(strict=True)
        worker_sha = _sha256(worker)
        remote_run_root = self._config.remote_root / "runs" / run_id
        request_name = f"{run_id}-{archive_sha256}.json"
        return _AutoDlPaths(
            local_root=local_root,
            local_request=local_root / "execution-request.json",
            local_profile=local_root / "connection-profile.json",
            local_environment=local_root / "environment-manifest.json",
            local_layout=local_root / "remote-layout.json",
            local_prepare_payload=local_root / "remote-prepare-payload.json",
            local_transfers=local_root / "transfers",
            remote_run_root=remote_run_root,
            remote_workspace=remote_run_root / "workspace",
            remote_worker=(
                self._config.remote_root
                / ".backend"
                / "workers"
                / worker_sha
                / "_autodl_worker.py"
            ),
            remote_staging_archive=(
                self._config.remote_root / ".staging" / f"{archive_sha256}.tar"
            ),
            remote_prepare_payload=(
                self._config.remote_root / ".requests" / request_name
            ),
        )

    def _safe_local_run_root(self, run_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,256}", run_id):
            raise ValueError("AutoDL run_id is not a safe path segment")
        root = (self._config.local_control_root / run_id).resolve(strict=False)
        root.relative_to(self._config.local_control_root.resolve(strict=True))
        return root


def _backend_status(
    backend_ref: BackendRunRef,
    response: dict[str, Any],
) -> BackendRunStatus:
    phase = BackendRunPhase(response["phase"])
    identity = response.get("process_identity")
    process_id = None
    process_create_time = None
    if identity is not None:
        process_id = int(identity["pid"])
        process_create_time = float(identity["start_ticks"])
    missing = tuple(response.get("missing_artifacts", ()))
    observed_at = datetime.fromisoformat(response["observed_at"])
    heartbeat_raw = response.get("heartbeat_at")
    checks = {
        "status_event_valid": bool(response.get("status_event_valid")),
        "process_identity_recorded": bool(
            response.get("target_identity_recorded")
        ),
        "required_artifacts_present": not missing,
    }
    exit_code = response.get("exit_code")
    return BackendRunStatus(
        backend_ref=backend_ref,
        phase=phase,
        observed_at=observed_at,
        process_id=process_id,
        process_create_time=process_create_time,
        exit_code=exit_code if isinstance(exit_code, int) else None,
        heartbeat_at=(
            None if heartbeat_raw is None else datetime.fromisoformat(heartbeat_raw)
        ),
        log_cursor=LogCursor(
            stdout_offset=int(response.get("stdout_offset", 0)),
            stderr_offset=int(response.get("stderr_offset", 0)),
            observed_at=observed_at,
        ),
        produced_artifacts=tuple(response.get("produced_artifacts", ())),
        checks=checks,
        detail=response.get("detail"),
    )


def _validate_remote_manifest(
    manifest: RunManifest,
    *,
    remote_root: PurePosixPath,
) -> Path:
    archive = _artifact_path(manifest.config_ref)
    if _sha256(archive) != manifest.config_ref.sha256:
        raise ValueError("AutoDL staging archive does not match ArtifactRef")
    _validate_staging_archive(archive)
    run_root = remote_root / "runs" / manifest.run_id
    working_directory = _confined_remote(
        PurePosixPath(manifest.working_directory),
        run_root,
    )
    if working_directory != run_root / "workspace":
        raise ValueError("AutoDL working directory must be the staged workspace")
    output_root = _confined_remote(
        PurePosixPath(manifest.output_root),
        working_directory,
    )
    if output_root == working_directory:
        raise ValueError("AutoDL output root must be below the workspace")
    interpreter = PurePosixPath(manifest.interpreter)
    if not interpreter.is_absolute() or manifest.command[0] != str(interpreter):
        raise ValueError("AutoDL command must start with the absolute interpreter")
    _validate_command_has_no_embedded_secret(manifest.command)
    for relative in manifest.expected_artifacts:
        _safe_relative(relative)
    return archive


def _validate_command_has_no_embedded_secret(command: tuple[str, ...]) -> None:
    forbidden = ("--password", "--passwd", "--token", "--api-key", "--secret")
    for argument in command:
        normalized = argument.casefold()
        if normalized in forbidden or any(
            normalized.startswith(f"{flag}=") for flag in forbidden
        ):
            raise ValueError("AutoDL command contains a secret-bearing argument")
        if re.search(r"://[^/@:\s]+:[^/@\s]+@", argument):
            raise ValueError("AutoDL command contains embedded URI credentials")


def _validate_staging_archive(path: Path) -> None:
    try:
        with tarfile.open(path, mode="r:*") as stream:
            names: set[str] = set()
            for member in stream.getmembers():
                relative = _safe_relative(member.name)
                normalized = str(PurePosixPath(*relative.parts))
                if normalized in names:
                    raise ValueError("staging archive contains duplicate paths")
                names.add(normalized)
                if member.issym() or member.islnk() or not (
                    member.isfile() or member.isdir()
                ):
                    raise ValueError("staging archive contains an unsafe member")
    except tarfile.TarError:
        raise ValueError("staging artifact must be a readable tar archive") from None


def _artifact_path(reference: ArtifactRef) -> Path:
    parsed = urlparse(reference.uri)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        raise ValueError("AutoDL staging ArtifactRef must use a local file URI")
    raw_path = unquote(parsed.path)
    if os.name == "nt" and len(raw_path) >= 3 and raw_path[0] == "/":
        if raw_path[2] == ":":
            raw_path = raw_path[1:]
    path = Path(raw_path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("AutoDL staging artifact must be a file")
    return path


def _extract_collection_archive(
    archive: Path,
    destination: Path,
    entries: tuple[dict[str, Any], ...],
) -> None:
    expected = {"source-manifest.json"}
    expected.update(
        str(PurePosixPath("artifacts") / entry["relative_path"])
        for entry in entries
    )
    with tarfile.open(archive, mode="r:*") as stream:
        members = tuple(stream.getmembers())
        names = {member.name for member in members}
        if names != expected or any(not member.isfile() for member in members):
            raise ValueError("remote collection archive member set is invalid")
        for member in members:
            relative = _safe_relative(member.name)
            target = (destination / relative).resolve(strict=False)
            target.relative_to(destination.resolve(strict=True))
            target.parent.mkdir(parents=True, exist_ok=True)
            source = stream.extractfile(member)
            if source is None:
                raise ValueError("remote archive member cannot be read")
            with target.open("xb") as target_stream:
                shutil.copyfileobj(source, target_stream)
    source_manifest = _read_json(destination / "source-manifest.json")
    if tuple(source_manifest.get("entries", ())) != entries:
        raise ValueError("remote source manifest entries do not match response")
    for entry in entries:
        path = destination / "artifacts" / _safe_relative(entry["relative_path"])
        if (
            not path.is_file()
            or path.stat().st_size != int(entry["size_bytes"])
            or _sha256(path) != entry["sha256"]
        ):
            raise ValueError("remote extracted artifact verification failed")


def _promote_collection(
    extraction_root: Path,
    destination: Path,
    *,
    run_id: str,
    archive_sha256: str,
    remote_source_sha256: str,
    entries: tuple[dict[str, Any], ...],
) -> ArtifactCollectionReport:
    marker_payload = {
        "run_id": run_id,
        "archive_sha256": archive_sha256,
        "remote_source_manifest_sha256": remote_source_sha256,
    }
    if destination.exists():
        if not destination.is_dir():
            raise FileExistsError("artifact destination is not a directory")
        marker = destination / "collection-request.json"
        if not marker.is_file():
            raise FileExistsError("artifact destination has no governed marker")
        _write_or_verify(marker, marker_payload)
    else:
        if not destination.is_absolute() or not destination.parent.is_dir():
            raise ValueError(
                "artifact destination parent must be absolute and existing"
            )
        destination.mkdir(exist_ok=False)
        marker = destination / "collection-request.json"
        _write_json_exclusive(marker, marker_payload)
    remote_source = extraction_root / "source-manifest.json"
    if _sha256(remote_source) != remote_source_sha256:
        raise ValueError("remote source manifest SHA-256 mismatch")
    promoted_source = destination / "remote-source-manifest.json"
    _copy_verified_no_overwrite(
        remote_source,
        promoted_source,
        remote_source_sha256,
    )
    artifact_refs: list[ArtifactRef] = []
    destination_entries: list[dict[str, Any]] = []
    for entry in entries:
        relative = _safe_relative(entry["relative_path"])
        source = extraction_root / "artifacts" / relative
        target = destination / relative
        target.resolve(strict=False).relative_to(destination.resolve(strict=True))
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy_verified_no_overwrite(source, target, entry["sha256"])
        reference = _artifact_ref(_artifact_id(run_id, entry["relative_path"]), target)
        artifact_refs.append(reference)
        destination_entries.append(
            {
                "relative_path": entry["relative_path"],
                "sha256": entry["sha256"],
                "size_bytes": entry["size_bytes"],
                "artifact_ref": reference.model_dump(mode="json"),
            }
        )
    destination_manifest = destination / "artifact-manifest.json"
    _write_or_verify(
        destination_manifest,
        {
            "run_id": run_id,
            "archive_sha256": archive_sha256,
            "entries": destination_entries,
        },
    )
    return ArtifactCollectionReport(
        run_id=run_id,
        status=ArtifactCollectionStatus.COMPLETE,
        artifact_refs=tuple(artifact_refs),
        source_manifest_ref=_artifact_ref(
            f"{run_id}-remote-source-manifest",
            promoted_source,
        ),
        destination_manifest_ref=_artifact_ref(
            f"{run_id}-destination-manifest",
            destination_manifest,
        ),
    )


def _existing_complete_collection(
    destination: Path,
    *,
    run_id: str,
    archive_sha256: str,
) -> ArtifactCollectionReport | None:
    if not destination.exists():
        return None
    if not destination.is_dir():
        raise FileExistsError("artifact destination is not a directory")
    marker = destination / "collection-request.json"
    if not marker.is_file():
        raise FileExistsError("artifact destination has no governed marker")
    marker_payload = _read_json(marker)
    if (
        marker_payload.get("run_id") != run_id
        or marker_payload.get("archive_sha256") != archive_sha256
    ):
        raise FileExistsError("artifact destination belongs to another collection")
    manifest_path = destination / "artifact-manifest.json"
    source_path = destination / "remote-source-manifest.json"
    if not manifest_path.is_file() or not source_path.is_file():
        return None
    payload = _read_json(manifest_path)
    if payload.get("run_id") != run_id:
        raise ValueError("existing destination manifest run_id mismatch")
    artifact_refs: list[ArtifactRef] = []
    for entry in payload.get("entries", ()):
        relative = _safe_relative(entry["relative_path"])
        path = destination / relative
        if not path.is_file() or _sha256(path) != entry["sha256"]:
            raise ValueError("existing destination artifact verification failed")
        artifact_refs.append(ArtifactRef.model_validate(entry["artifact_ref"]))
    if not artifact_refs:
        raise ValueError("existing destination manifest has no artifacts")
    return ArtifactCollectionReport(
        run_id=run_id,
        status=ArtifactCollectionStatus.COMPLETE,
        artifact_refs=tuple(artifact_refs),
        source_manifest_ref=_artifact_ref(
            f"{run_id}-remote-source-manifest",
            source_path,
        ),
        destination_manifest_ref=_artifact_ref(
            f"{run_id}-destination-manifest",
            manifest_path,
        ),
    )


def _copy_verified_no_overwrite(source: Path, target: Path, sha256: str) -> None:
    if target.exists():
        if not target.is_file() or _sha256(target) != sha256:
            raise FileExistsError("existing promoted artifact differs")
        return
    shutil.copy2(source, target)
    if _sha256(target) != sha256:
        raise OSError("promoted artifact verification failed")


def _write_or_verify(path: Path, payload: dict[str, Any]) -> None:
    encoded = _canonical_json(payload)
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError("governed AutoDL manifest differs")
        return
    try:
        _write_json_exclusive(path, payload)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError("governed AutoDL manifest differs") from None


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


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("governed AutoDL JSON must be an object")
    return payload


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


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        raise ValueError("artifact path must be safe and relative")
    return path


def _validate_remote_path(path: PurePosixPath) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("AutoDL remote path must be absolute and confined")
    if any("\x00" in part or "\n" in part for part in path.parts):
        raise ValueError("AutoDL remote path contains a control character")


def _confined_remote(path: PurePosixPath, root: PurePosixPath) -> PurePosixPath:
    _validate_remote_path(path)
    if path != root and root not in path.parents:
        raise ValueError("AutoDL remote path escapes the governed root")
    return path


def _credential_like_name(name: str) -> bool:
    normalized = name.casefold().replace("-", "_")
    return bool(
        re.search(
            r"(^|_)(password|passwd|token|secret|api_key|private_key|access_key)($|_)",
            normalized,
        )
    )


def _require_sha256(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("remote response contains an invalid SHA-256")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

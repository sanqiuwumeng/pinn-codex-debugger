"""Run one credential-safe, bounded AutoDL backend qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tarfile
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
sys.path.insert(0, str(ORCHESTRATOR_SRC))

from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactCollectionSpec,
    ArtifactCollectionStatus,
    ArtifactRef,
    RunManifest,
    RunSubmissionStatus,
    SshConnectionProfile,
)
from pinn_strategy_system.execution import (  # noqa: E402
    AutoDlSshBackendConfig,
    AutoDlSshRunnerBackend,
    ManifestFirstRunner,
    RunLaunchUncertainError,
    SQLiteRunRegistry,
    SshTransportError,
    SystemOpenSshRuntime,
    SystemOpenSshTransport,
)


RUN_ID = "autodl-backend-qualification-20260716-v4"
WORKFLOW_ID = "autodl-backend-qualification-workflow"
EXPERIMENT_ID = "autodl-backend-qualification-experiment"
FIXTURE = """\
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=False)
time.sleep(3.0)
(output / "metrics.json").write_text(
    json.dumps({"bounded_value": 0.125}, sort_keys=True),
    encoding="utf-8",
)
(output / "run_status.json").write_text(
    json.dumps({"status": "completed"}, sort_keys=True),
    encoding="utf-8",
)
print("bounded AutoDL backend qualification completed")
"""


class LoseLaunchResponseTransport:
    def __init__(self, transport: SystemOpenSshTransport) -> None:
        self._transport = transport
        self.launch_count = 0

    def ensure_directory(self, remote_path: PurePosixPath) -> None:
        self._transport.ensure_directory(remote_path)

    def install_content(
        self,
        local_path: Path,
        remote_path: PurePosixPath,
        sha256: str,
    ) -> None:
        self._transport.install_content(local_path, remote_path, sha256)

    def invoke(
        self,
        worker_path: PurePosixPath,
        arguments: tuple[str, ...],
    ) -> dict:
        response = self._transport.invoke(worker_path, arguments)
        if arguments[0] == "launch":
            self.launch_count += 1
            raise SshTransportError("simulated lost launch response")
        return response

    def download(self, remote_path: PurePosixPath, local_path: Path) -> None:
        self._transport.download(remote_path, local_path)


class LoseFirstStatusTransport:
    def __init__(self, transport: SystemOpenSshTransport) -> None:
        self._transport = transport
        self.status_failures = 0

    def ensure_directory(self, remote_path: PurePosixPath) -> None:
        self._transport.ensure_directory(remote_path)

    def install_content(
        self,
        local_path: Path,
        remote_path: PurePosixPath,
        sha256: str,
    ) -> None:
        self._transport.install_content(local_path, remote_path, sha256)

    def invoke(
        self,
        worker_path: PurePosixPath,
        arguments: tuple[str, ...],
    ) -> dict:
        if arguments[0] == "status" and self.status_failures == 0:
            self.status_failures += 1
            raise SshTransportError("simulated status disconnect")
        return self._transport.invoke(worker_path, arguments)

    def download(self, remote_path: PurePosixPath, local_path: Path) -> None:
        self._transport.download(remote_path, local_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh-executable", type=Path, required=True)
    parser.add_argument("--scp-executable", type=Path, required=True)
    parser.add_argument("--identity-file", type=Path, required=True)
    parser.add_argument("--known-hosts-file", type=Path, required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--remote-python", type=PurePosixPath, required=True)
    parser.add_argument("--remote-root", type=PurePosixPath, required=True)
    parser.add_argument("--host-fingerprint-sha256", required=True)
    parser.add_argument("--identity-fingerprint-sha256", required=True)
    parser.add_argument("--local-result-root", type=Path, required=True)
    arguments = parser.parse_args()

    local_root = arguments.local_result_root.resolve(strict=False)
    if local_root.exists():
        raise FileExistsError("qualification result root already exists")
    local_root.mkdir(parents=True)
    control_root = local_root / "control"
    control_root.mkdir()
    fixture = local_root / "bounded_remote_fixture.py"
    fixture.write_text(FIXTURE, encoding="utf-8")
    staging_archive = local_root / "bounded-staging.tar"
    with tarfile.open(staging_archive, mode="w") as stream:
        stream.add(fixture, arcname="job.py")

    profile = SshConnectionProfile(
        profile_id="autodl-a",
        host_key_fingerprint_sha256=arguments.host_fingerprint_sha256,
        identity_key_fingerprint_sha256=arguments.identity_fingerprint_sha256,
    )
    local_environment = _local_openssh_environment()
    runtime = SystemOpenSshRuntime(
        profile_id=profile.profile_id,
        ssh_executable=arguments.ssh_executable.resolve(strict=True),
        scp_executable=arguments.scp_executable.resolve(strict=True),
        username=arguments.username,
        hostname=arguments.hostname,
        port=arguments.port,
        identity_file=arguments.identity_file.resolve(strict=True),
        known_hosts_file=arguments.known_hosts_file.resolve(strict=True),
        remote_python=arguments.remote_python,
        local_working_directory=local_root,
        environment=local_environment,
        connect_timeout_seconds=15,
        operation_timeout_seconds=120,
    )
    transport = SystemOpenSshTransport(runtime)
    remote_environment = (
        ("HOME", "/root"),
        (
            "PATH",
            "/root/miniconda3/bin:/usr/local/sbin:/usr/local/bin:"
            "/usr/sbin:/usr/bin:/sbin:/bin",
        ),
        ("PYTHONUTF8", "1"),
    )
    backend_config = AutoDlSshBackendConfig(
        connection_profile=profile,
        remote_root=arguments.remote_root,
        local_control_root=control_root,
        remote_environment=remote_environment,
        environment_allowlist=tuple(name for name, _ in remote_environment),
        heartbeat_interval_seconds=0.5,
        heartbeat_stale_after_seconds=5.0,
    )
    registry = SQLiteRunRegistry(local_root / "qualification.sqlite3")
    remote_run_root = arguments.remote_root / "runs" / RUN_ID
    remote_workspace = remote_run_root / "workspace"
    output_root = remote_workspace / "outputs"
    manifest = RunManifest(
        run_id=RUN_ID,
        workflow_id=WORKFLOW_ID,
        experiment_id=EXPERIMENT_ID,
        idempotency_key=f"{EXPERIMENT_ID}-bounded-v1",
        environment_name="autodl-base-python-bounded",
        interpreter=str(arguments.remote_python),
        working_directory=str(remote_workspace),
        command=(
            str(arguments.remote_python),
            str(remote_workspace / "job.py"),
            str(output_root),
        ),
        config_ref=_artifact("bounded-staging", staging_archive),
        output_root=str(output_root),
        expected_artifacts=("metrics.json", "run_status.json"),
        checkpoint_policy="No checkpoint for the three-second qualification.",
        rollback_plan="Preserve remote and local qualification evidence.",
    )
    approval = ApprovalRecord(
        approval_id="autodl-backend-qualification-approval",
        workflow_id=WORKFLOW_ID,
        kind=ApprovalKind.EXPERIMENT,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=datetime(2026, 7, 16, tzinfo=UTC),
        scope="Phase 2 bounded AutoDL backend qualification only",
    )

    lost_transport = LoseLaunchResponseTransport(transport)
    first_runner = ManifestFirstRunner(
        registry,
        AutoDlSshRunnerBackend(backend_config, lost_transport),
    )
    launch_response_lost = False
    try:
        first_runner.submit(manifest, approval)
    except RunLaunchUncertainError:
        launch_response_lost = True
    if not launch_response_lost:
        raise RuntimeError("qualification did not simulate lost launch response")

    status_transport = LoseFirstStatusTransport(transport)
    second_runner = ManifestFirstRunner(
        registry,
        AutoDlSshRunnerBackend(backend_config, status_transport),
    )
    duplicate = second_runner.submit(manifest, approval)
    disconnected = second_runner.reconcile(manifest.idempotency_key)
    if disconnected.status is not RunSubmissionStatus.RUNNING_UNKNOWN:
        raise RuntimeError("simulated status disconnect was not preserved as unknown")

    final_backend = AutoDlSshRunnerBackend(backend_config, transport)
    final_runner = ManifestFirstRunner(registry, final_backend)
    deadline = time.monotonic() + 30.0
    terminal = None
    while time.monotonic() < deadline:
        terminal = final_runner.reconcile(manifest.idempotency_key)
        if terminal.status in (
            RunSubmissionStatus.COMPLETED,
            RunSubmissionStatus.FAILED,
            RunSubmissionStatus.CANCELLED,
        ):
            break
        time.sleep(0.5)
    if terminal is None or terminal.status is not RunSubmissionStatus.COMPLETED:
        raise RuntimeError("bounded remote qualification did not complete")
    assert terminal.backend_ref is not None
    destination = local_root / "authoritative" / RUN_ID
    destination.parent.mkdir()
    collected = final_runner.collect(
        manifest.idempotency_key,
        ArtifactCollectionSpec(
            run_id=RUN_ID,
            backend_ref=terminal.backend_ref,
            destination_root=str(destination),
            required_artifacts=manifest.expected_artifacts,
        ),
    )
    if (
        collected.collection_report is None
        or collected.collection_report.status
        is not ArtifactCollectionStatus.COMPLETE
    ):
        raise RuntimeError("bounded remote collection did not complete")
    repeated = final_backend.collect(
        terminal.backend_ref,
        ArtifactCollectionSpec(
            run_id=RUN_ID,
            backend_ref=terminal.backend_ref,
            destination_root=str(destination),
            required_artifacts=manifest.expected_artifacts,
        ),
    )
    checks = {
        "launch_response_lost": launch_response_lost,
        "duplicate_submission": duplicate.duplicate,
        "single_remote_launch": lost_transport.launch_count == 1,
        "status_disconnect_observed": status_transport.status_failures == 1,
        "reconnected_completion": terminal.status
        is RunSubmissionStatus.COMPLETED,
        "collection_complete": collected.collection_report.status
        is ArtifactCollectionStatus.COMPLETE,
        "collection_idempotent": repeated.status
        is ArtifactCollectionStatus.COMPLETE,
        "metrics_present": (destination / "metrics.json").is_file(),
        "run_status_present": (destination / "run_status.json").is_file(),
        "destination_manifest_present": (
            destination / "artifact-manifest.json"
        ).is_file(),
    }
    if not all(checks.values()):
        raise RuntimeError("bounded AutoDL qualification checks failed")
    report = {
        "schema_version": "1.0",
        "profile": profile.model_dump(mode="json"),
        "run_id": RUN_ID,
        "remote_root": str(arguments.remote_root),
        "remote_python": str(arguments.remote_python),
        "checks": checks,
        "status": "PASS",
        "artifacts": {
            relative: {
                "sha256": _sha256(destination / relative),
                "size_bytes": (destination / relative).stat().st_size,
            }
            for relative in manifest.expected_artifacts
        },
    }
    report_path = local_root / "qualification-report.json"
    _write_json_exclusive(report_path, report)
    print(
        json.dumps(
            {
                "status": "PASS",
                "report": str(report_path),
                "remote_launch_count": lost_transport.launch_count,
            },
            sort_keys=True,
        )
    )


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


def _artifact(artifact_id: str, path: Path) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        uri=path.resolve().as_uri(),
        sha256=_sha256(path),
        size_bytes=path.stat().st_size,
    )


def _write_json_exclusive(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(
            payload,
            stream,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        stream.write("\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactCollectionSpec,
    ArtifactCollectionStatus,
    ArtifactRef,
    BackendRunPhase,
    RunCancellationRequest,
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


REMOTE_ROOT = PurePosixPath("/root/pinn-strategy-phase2")


class FakeAutoDlTransport:
    def __init__(self, collection_archive: Path, collection_response: dict) -> None:
        self.collection_archive = collection_archive
        self.collection_response = collection_response
        self.ensure_calls: list[PurePosixPath] = []
        self.install_calls: list[tuple[Path, PurePosixPath, str]] = []
        self.invoke_calls: list[tuple[PurePosixPath, tuple[str, ...]]] = []
        self.launch_count = 0
        self.fail_launch_response = False
        self.interrupt_download = False
        self.phase = BackendRunPhase.RUNNING

    def ensure_directory(self, remote_path: PurePosixPath) -> None:
        self.ensure_calls.append(remote_path)

    def install_content(
        self,
        local_path: Path,
        remote_path: PurePosixPath,
        sha256: str,
    ) -> None:
        if _sha256(local_path) != sha256:
            raise AssertionError("fake transport received an invalid content hash")
        self.install_calls.append((local_path, remote_path, sha256))

    def invoke(
        self,
        worker_path: PurePosixPath,
        arguments: tuple[str, ...],
    ) -> dict:
        self.invoke_calls.append((worker_path, arguments))
        operation = arguments[0]
        if operation == "prepare":
            return {
                "status": "prepared",
                "run_id": "autodl-run-1",
                "staging_archive_sha256": self._archive_sha_from_installs(),
            }
        if operation == "launch":
            self.launch_count += 1
            if self.fail_launch_response:
                raise SshTransportError("simulated disconnect")
            return {"status": "launched", "launcher_identity": _identity(7001)}
        if operation == "status":
            return self._status_response()
        if operation == "cancel":
            self.phase = BackendRunPhase.CANCELLED
            return self._status_response(exit_code=-15)
        if operation == "collect":
            return self.collection_response
        raise AssertionError(f"unexpected fake operation: {operation}")

    def download(self, remote_path: PurePosixPath, local_path: Path) -> None:
        if self.interrupt_download:
            local_path.write_bytes(self.collection_archive.read_bytes()[:32])
            raise SshTransportError("simulated transfer interruption")
        shutil.copy2(self.collection_archive, local_path)

    def _archive_sha_from_installs(self) -> str:
        for local_path, remote_path, sha256 in self.install_calls:
            if remote_path.parent == REMOTE_ROOT / ".staging":
                return sha256
        raise AssertionError("staging archive was not installed")

    def _status_response(self, exit_code: int | None = None) -> dict:
        completed = self.phase is BackendRunPhase.COMPLETED
        cancelled = self.phase is BackendRunPhase.CANCELLED
        return {
            "phase": self.phase.value,
            "observed_at": datetime.now(UTC).isoformat(),
            "process_identity": _identity(7002),
            "target_identity_recorded": True,
            "exit_code": (
                0 if completed else exit_code if cancelled else None
            ),
            "heartbeat_at": datetime.now(UTC).isoformat(),
            "stdout_offset": 128,
            "stderr_offset": 0,
            "produced_artifacts": (
                ["metrics.json", "run_status.json"] if completed else []
            ),
            "missing_artifacts": (
                [] if completed else ["metrics.json", "run_status.json"]
            ),
            "status_event_valid": True,
            "detail": None,
        }


class AutoDlSshBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.control_root = self.root / "control"
        self.control_root.mkdir()
        self.staging_archive = self.root / "staging.tar"
        fixture = self.root / "job.py"
        fixture.write_text("print('bounded remote fixture')\n", encoding="utf-8")
        with tarfile.open(self.staging_archive, mode="w") as stream:
            stream.add(fixture, arcname="job.py")
        (
            self.collection_archive,
            self.collection_response,
        ) = _collection_archive(self.root)
        self.transport = FakeAutoDlTransport(
            self.collection_archive,
            self.collection_response,
        )
        self.backend = AutoDlSshRunnerBackend(
            AutoDlSshBackendConfig(
                connection_profile=SshConnectionProfile(
                    profile_id="autodl-a",
                    host_key_fingerprint_sha256="b" * 64,
                    identity_key_fingerprint_sha256="c" * 64,
                ),
                remote_root=REMOTE_ROOT,
                local_control_root=self.control_root,
                remote_environment=(
                    ("HOME", "/root"),
                    ("PATH", "/usr/local/bin:/usr/bin:/bin"),
                    ("PYTHONUTF8", "1"),
                ),
                environment_allowlist=("HOME", "PATH", "PYTHONUTF8"),
                heartbeat_interval_seconds=0.1,
                heartbeat_stale_after_seconds=1.0,
            ),
            self.transport,
        )
        self.registry = SQLiteRunRegistry(self.root / "runs.sqlite")
        self.runner = ManifestFirstRunner(self.registry, self.backend)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_successful_remote_lifecycle_and_verified_collection(self) -> None:
        manifest = self._manifest()
        submitted = self.runner.submit(manifest, self._approval())
        self.transport.phase = BackendRunPhase.COMPLETED
        completed = self.runner.reconcile(manifest.idempotency_key)
        assert submitted.backend_ref is not None
        destination = self.root / "authoritative" / manifest.run_id
        destination.parent.mkdir()

        collected = self.runner.collect(
            manifest.idempotency_key,
            ArtifactCollectionSpec(
                run_id=manifest.run_id,
                backend_ref=submitted.backend_ref,
                destination_root=str(destination),
                required_artifacts=manifest.expected_artifacts,
            ),
        )

        self.assertEqual(completed.status, RunSubmissionStatus.COMPLETED)
        self.assertEqual(collected.status, RunSubmissionStatus.COMPLETED)
        self.assertEqual(
            collected.collection_report.status,
            ArtifactCollectionStatus.COMPLETE,
        )
        self.assertTrue((destination / "artifact-manifest.json").is_file())
        profile_payload = json.loads(
            (
                self.control_root / manifest.run_id / "connection-profile.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(
            {"hostname", "username", "port", "password", "identity_file"}
            & profile_payload.keys()
        )

    def test_lost_launch_response_reconciles_without_remote_relaunch(self) -> None:
        manifest = self._manifest()
        approval = self._approval()
        self.transport.fail_launch_response = True

        with self.assertRaises(RunLaunchUncertainError):
            self.runner.submit(manifest, approval)
        duplicate = self.runner.submit(manifest, approval)
        reconciled = self.runner.reconcile(manifest.idempotency_key)

        self.assertEqual(self.transport.launch_count, 1)
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(duplicate.status, RunSubmissionStatus.RUNNING_UNKNOWN)
        self.assertEqual(reconciled.status, RunSubmissionStatus.RUNNING)

    def test_approved_cancel_uses_remote_worker(self) -> None:
        manifest = self._manifest()
        self.runner.submit(manifest, self._approval())

        cancelled = self.runner.cancel(
            manifest.idempotency_key,
            self._cancellation(manifest),
        )

        self.assertEqual(cancelled.status, RunSubmissionStatus.CANCELLED)
        self.assertTrue(
            any(call[1][0] == "cancel" for call in self.transport.invoke_calls)
        )

    def test_interrupted_download_remains_partial_in_quarantine(self) -> None:
        manifest = self._manifest()
        submitted = self.runner.submit(manifest, self._approval())
        self.transport.phase = BackendRunPhase.COMPLETED
        self.runner.reconcile(manifest.idempotency_key)
        self.transport.interrupt_download = True
        assert submitted.backend_ref is not None
        destination = self.root / "authoritative" / manifest.run_id
        destination.parent.mkdir()

        report = self.backend.collect(
            submitted.backend_ref,
            ArtifactCollectionSpec(
                run_id=manifest.run_id,
                backend_ref=submitted.backend_ref,
                destination_root=str(destination),
                required_artifacts=manifest.expected_artifacts,
            ),
        )

        self.assertEqual(report.status, ArtifactCollectionStatus.PARTIAL)
        transfers = self.control_root / manifest.run_id / "transfers"
        self.assertEqual(len(tuple(transfers.glob("*.partial.tar"))), 1)
        self.assertFalse(destination.exists())

    def test_system_transport_errors_redact_endpoint_and_key_path(self) -> None:
        ssh = self.root / "ssh.exe"
        scp = self.root / "scp.exe"
        identity = self.root / "identity"
        known_hosts = self.root / "known_hosts"
        for path in (ssh, scp, identity, known_hosts):
            path.write_text("fixture\n", encoding="utf-8")
        runtime = SystemOpenSshRuntime(
            profile_id="redaction-test",
            ssh_executable=ssh,
            scp_executable=scp,
            username="sensitive-user",
            hostname="sensitive-host.example",
            port=2222,
            identity_file=identity,
            known_hosts_file=known_hosts,
            remote_python=PurePosixPath("/usr/bin/python3"),
            local_working_directory=self.root,
            environment=(("SYSTEMROOT", "C:/Windows"),),
            operation_timeout_seconds=1,
        )
        transport = SystemOpenSshTransport(runtime)

        with self.assertRaises(SshTransportError) as captured:
            transport.ensure_directory(PurePosixPath("/root/fixture"))

        rendered = f"{runtime!r} {captured.exception}"
        self.assertNotIn("sensitive-user", rendered)
        self.assertNotIn("sensitive-host", rendered)
        self.assertNotIn(str(identity), rendered)

    def _manifest(self) -> RunManifest:
        run_root = REMOTE_ROOT / "runs" / "autodl-run-1"
        workspace = run_root / "workspace"
        return RunManifest(
            run_id="autodl-run-1",
            workflow_id="autodl-workflow-1",
            experiment_id="autodl-experiment-1",
            idempotency_key="autodl-idempotency-1",
            environment_name="autodl-bounded",
            interpreter="/usr/bin/python3",
            working_directory=str(workspace),
            command=(
                "/usr/bin/python3",
                str(workspace / "job.py"),
                str(workspace / "outputs"),
            ),
            config_ref=_artifact("staging-archive", self.staging_archive),
            output_root=str(workspace / "outputs"),
            expected_artifacts=("metrics.json", "run_status.json"),
            checkpoint_policy="Bounded remote fixture only.",
            rollback_plan="Retain remote and quarantined evidence.",
        )

    @staticmethod
    def _approval() -> ApprovalRecord:
        return ApprovalRecord(
            approval_id="autodl-approval-1",
            workflow_id="autodl-workflow-1",
            kind=ApprovalKind.EXPERIMENT,
            decision=ApprovalDecision.APPROVED,
            approved_by="test-user",
            approved_at=datetime(2026, 7, 16, tzinfo=UTC),
            scope="bounded AutoDL backend qualification",
        )

    @staticmethod
    def _cancellation(manifest: RunManifest) -> RunCancellationRequest:
        return RunCancellationRequest(
            run_id=manifest.run_id,
            workflow_id=manifest.workflow_id,
            requested_at=datetime.now(UTC),
            reason="Bounded AutoDL cancellation qualification.",
            approval=ApprovalRecord(
                approval_id="autodl-cancel-approval-1",
                workflow_id=manifest.workflow_id,
                kind=ApprovalKind.RUN_CANCELLATION,
                decision=ApprovalDecision.APPROVED,
                approved_by="test-user",
                approved_at=datetime.now(UTC),
                scope=f"run:{manifest.run_id}:cancel",
            ),
        )


def _collection_archive(root: Path) -> tuple[Path, dict]:
    source_root = root / "remote-collection-source"
    artifact_root = source_root / "artifacts"
    artifact_root.mkdir(parents=True)
    payloads = {
        "metrics.json": b'{"loss": 0.125}',
        "run_status.json": b'{"status": "completed"}',
    }
    entries = []
    for relative, content in payloads.items():
        path = artifact_root / relative
        path.write_bytes(content)
        entries.append(
            {
                "relative_path": relative,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    source_manifest = source_root / "source-manifest.json"
    source_manifest.write_text(
        json.dumps(
            {
                "run_id": "autodl-run-1",
                "output_root": str(REMOTE_ROOT / "runs" / "autodl-run-1"),
                "entries": entries,
                "missing": [],
            },
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    archive = root / "remote-collection.tar"
    with tarfile.open(archive, mode="w") as stream:
        stream.add(source_manifest, arcname="source-manifest.json")
        for entry in entries:
            stream.add(
                artifact_root / entry["relative_path"],
                arcname=f"artifacts/{entry['relative_path']}",
            )
    response = {
        "status": "COMPLETE",
        "archive_path": str(
            REMOTE_ROOT
            / "runs"
            / "autodl-run-1"
            / "collections"
            / "artifacts.tar"
        ),
        "archive_sha256": _sha256(archive),
        "archive_size_bytes": archive.stat().st_size,
        "source_manifest_sha256": _sha256(source_manifest),
        "entries": entries,
        "missing_artifacts": [],
    }
    return archive, response


def _identity(pid: int) -> dict:
    return {
        "pid": pid,
        "start_ticks": 123456,
        "recorded_at": datetime.now(UTC).isoformat(),
    }


def _artifact(artifact_id: str, path: Path) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        uri=path.resolve().as_uri(),
        sha256=_sha256(path),
        size_bytes=path.stat().st_size,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    unittest.main()

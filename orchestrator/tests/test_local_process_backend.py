from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import psutil

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
    ExecutionRequest,
    RunCancellationRequest,
    RunManifest,
    RunSubmissionStatus,
)
from pinn_strategy_system.execution import (  # noqa: E402
    LocalProcessBackendConfig,
    LocalProcessRunnerBackend,
    ManifestFirstRunner,
    SQLiteRunRegistry,
)


WORKER_FIXTURE = """\
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

output = Path(sys.argv[1])
mode = sys.argv[2]
if mode == "sleep":
    time.sleep(30)
elif mode == "nonzero":
    print("bounded failure", file=sys.stderr)
    raise SystemExit(7)
else:
    output.mkdir(parents=True, exist_ok=False)
    (output / "metrics.json").write_text(
        json.dumps({"loss": 0.25}), encoding="utf-8"
    )
    if mode != "missing":
        (output / "run_status.json").write_text(
            json.dumps({"status": "completed"}), encoding="utf-8"
        )
    print("bounded fixture completed")
"""


class LocalProcessBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.run_root = self.root / "backend-runs"
        self.run_root.mkdir()
        self.work_root = self.root / "work"
        self.work_root.mkdir()
        self.script = self.work_root / "bounded_fixture.py"
        self.script.write_text(WORKER_FIXTURE, encoding="utf-8")
        self.config_file = self.work_root / "config.json"
        self.config_file.write_text("{}\n", encoding="utf-8")
        environment = _explicit_test_environment()
        self.backend = LocalProcessRunnerBackend(
            LocalProcessBackendConfig(
                run_root=self.run_root,
                launcher_interpreter=Path(sys.executable).resolve(),
                environment=environment,
                environment_allowlist=tuple(name for name, _ in environment),
                heartbeat_interval_seconds=0.02,
                heartbeat_stale_after_seconds=0.15,
                cancellation_timeout_seconds=2.0,
            )
        )
        self.registry = SQLiteRunRegistry(self.root / "runs.sqlite")
        self.runner = ManifestFirstRunner(self.registry, self.backend)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_success_reconciles_logs_and_collects_idempotently(self) -> None:
        manifest = self._manifest("success-run", "success")
        submitted = self.runner.submit(manifest, self._approval())
        completed = self._wait_for_terminal(manifest.idempotency_key)

        self.assertEqual(completed.status, RunSubmissionStatus.COMPLETED)
        status = completed.last_backend_status
        assert status is not None
        self.assertEqual(status.phase, BackendRunPhase.COMPLETED)
        self.assertEqual(status.exit_code, 0)
        self.assertEqual(status.produced_artifacts, manifest.expected_artifacts)
        self.assertGreater(status.log_cursor.stdout_offset, 0)
        assert submitted.backend_ref is not None
        spec = ArtifactCollectionSpec(
            run_id=manifest.run_id,
            backend_ref=submitted.backend_ref,
            destination_root=str(self.root / "artifacts-success"),
            required_artifacts=manifest.expected_artifacts,
        )

        collected = self.runner.collect(manifest.idempotency_key, spec)
        repeated = self.backend.collect(submitted.backend_ref, spec)

        self.assertEqual(collected.status, RunSubmissionStatus.COMPLETED)
        self.assertEqual(repeated.status, ArtifactCollectionStatus.COMPLETE)
        self.assertTrue(
            (self.root / "artifacts-success" / "artifact-manifest.json").is_file()
        )

    def test_nonzero_exit_is_terminal_failure(self) -> None:
        manifest = self._manifest("nonzero-run", "nonzero")
        self.runner.submit(manifest, self._approval())

        failed = self._wait_for_terminal(manifest.idempotency_key)

        self.assertEqual(failed.status, RunSubmissionStatus.FAILED)
        assert failed.last_backend_status is not None
        self.assertEqual(failed.last_backend_status.exit_code, 7)

    def test_exit_zero_with_missing_artifact_is_failure(self) -> None:
        manifest = self._manifest("missing-run", "missing")
        self.runner.submit(manifest, self._approval())

        failed = self._wait_for_terminal(manifest.idempotency_key)

        self.assertEqual(failed.status, RunSubmissionStatus.FAILED)
        assert failed.last_backend_status is not None
        self.assertEqual(failed.last_backend_status.exit_code, 0)
        self.assertIn("missing artifacts", failed.last_backend_status.detail)

    def test_duplicate_submit_does_not_relaunch_and_cancel_is_scoped(self) -> None:
        manifest = self._manifest("cancel-run", "sleep")
        approval = self._approval()
        first = self.runner.submit(manifest, approval)
        second = self.runner.submit(manifest, approval)
        assert first.backend_ref is not None
        identity_path = self.run_root / manifest.run_id / "launcher-identity.json"
        _wait_for_path(identity_path)
        launcher_pid = json.loads(identity_path.read_text(encoding="utf-8"))["pid"]

        cancelled = self.runner.cancel(
            manifest.idempotency_key,
            self._cancellation(manifest),
        )

        self.assertTrue(second.duplicate)
        self.assertEqual(second.backend_ref, first.backend_ref)
        self.assertEqual(cancelled.status, RunSubmissionStatus.CANCELLED)
        self.assertFalse(psutil.pid_exists(launcher_pid))
        self.assertTrue(
            (self.run_root / manifest.run_id / "cancellation-approval.json").is_file()
        )

    def test_stale_heartbeat_and_launch_timeout_become_unknown(self) -> None:
        running = self._manual_status("stale-run", BackendRunPhase.RUNNING, age=1.0)
        starting = self._manual_status(
            "launch-timeout-run",
            BackendRunPhase.PREPARED,
            age=1.0,
        )

        self.assertEqual(running.phase, BackendRunPhase.RUNNING_UNKNOWN)
        self.assertEqual(starting.phase, BackendRunPhase.RUNNING_UNKNOWN)
        self.assertEqual(running.detail, "heartbeat is stale")

    def test_cancel_without_process_identity_remains_unknown(self) -> None:
        manifest = self._manifest("cancel-unknown-run", "sleep")
        prepared = self.backend.prepare(
            ExecutionRequest(
                request_id="execution-cancel-unknown-run",
                manifest=manifest,
                approval=self._approval(),
            )
        )

        status = self.backend.cancel(
            prepared.backend_ref,
            self._cancellation(manifest),
        )

        self.assertEqual(status.phase, BackendRunPhase.RUNNING_UNKNOWN)
        self.assertFalse(status.checks["process_identity_recorded"])
        self.assertFalse(status.checks["process_tree_stopped"])

    def test_pid_reuse_identity_mismatch_becomes_unknown(self) -> None:
        manifest = self._manifest("pid-reuse-run", "success")
        prepared = self.backend.prepare(
            ExecutionRequest(
                request_id="execution-pid-reuse-run",
                manifest=manifest,
                approval=self._approval(),
            )
        )
        run_root = Path(prepared.staging_root)
        identity = {
            "pid": os.getpid(),
            "create_time": psutil.Process().create_time() - 100.0,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        (run_root / "process-identity.json").write_text(
            json.dumps(identity), encoding="utf-8"
        )
        _write_status(run_root, BackendRunPhase.RUNNING, age=0.0)

        status = self.backend.reconcile(prepared.backend_ref)

        self.assertEqual(status.phase, BackendRunPhase.RUNNING_UNKNOWN)
        self.assertIn("not live", status.detail)

    def test_interrupted_collection_is_partial_and_resumable(self) -> None:
        manifest = self._manifest("partial-copy-run", "success")
        submitted = self.runner.submit(manifest, self._approval())
        self._wait_for_terminal(manifest.idempotency_key)
        assert submitted.backend_ref is not None
        spec = ArtifactCollectionSpec(
            run_id=manifest.run_id,
            backend_ref=submitted.backend_ref,
            destination_root=str(self.root / "artifacts-partial"),
            required_artifacts=manifest.expected_artifacts,
        )
        real_copy = shutil.copy2
        copy_count = 0

        def interrupt_second_copy(source, destination):
            nonlocal copy_count
            copy_count += 1
            if copy_count == 2:
                raise OSError("injected copy interruption")
            return real_copy(source, destination)

        with patch(
            "pinn_strategy_system.execution.local_process.shutil.copy2",
            side_effect=interrupt_second_copy,
        ):
            partial = self.backend.collect(submitted.backend_ref, spec)
        resumed = self.backend.collect(submitted.backend_ref, spec)

        self.assertEqual(partial.status, ArtifactCollectionStatus.PARTIAL)
        self.assertEqual(len(partial.artifact_refs), 1)
        self.assertEqual(resumed.status, ArtifactCollectionStatus.COMPLETE)

    def _manual_status(
        self,
        run_id: str,
        phase: BackendRunPhase,
        *,
        age: float,
    ):
        manifest = self._manifest(run_id, "success")
        prepared = self.backend.prepare(
            ExecutionRequest(
                request_id=f"execution-{run_id}",
                manifest=manifest,
                approval=self._approval(),
            )
        )
        run_root = Path(prepared.staging_root)
        identity = {
            "pid": os.getpid(),
            "create_time": psutil.Process().create_time(),
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        (run_root / "launcher-identity.json").write_text(
            json.dumps(identity), encoding="utf-8"
        )
        _write_status(run_root, phase, age=age)
        return self.backend.reconcile(prepared.backend_ref)

    def _manifest(self, run_id: str, mode: str) -> RunManifest:
        output_root = self.root / f"output-{run_id}"
        return RunManifest(
            run_id=run_id,
            workflow_id="workflow-local-backend",
            experiment_id=f"experiment-{run_id}",
            idempotency_key=f"idempotency-{run_id}",
            environment_name="pinn_strategy_orchestrator-test",
            interpreter=str(Path(sys.executable).resolve()),
            working_directory=str(self.work_root),
            command=(
                str(Path(sys.executable).resolve()),
                str(self.script),
                str(output_root),
                mode,
            ),
            config_ref=_artifact_ref(self.config_file),
            output_root=str(output_root),
            expected_artifacts=("metrics.json", "run_status.json"),
            checkpoint_policy="No checkpoint for bounded backend fixture.",
            rollback_plan="Retain manifests and bounded fixture evidence.",
        )

    @staticmethod
    def _approval() -> ApprovalRecord:
        return ApprovalRecord(
            approval_id="approval-local-backend",
            workflow_id="workflow-local-backend",
            kind=ApprovalKind.EXPERIMENT,
            decision=ApprovalDecision.APPROVED,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
            scope="bounded local backend qualification only",
        )

    @staticmethod
    def _cancellation(manifest: RunManifest) -> RunCancellationRequest:
        return RunCancellationRequest(
            run_id=manifest.run_id,
            workflow_id=manifest.workflow_id,
            requested_at=datetime.now(UTC),
            reason="Bounded cancellation qualification.",
            approval=ApprovalRecord(
                approval_id="approval-cancel-local-backend",
                workflow_id=manifest.workflow_id,
                kind=ApprovalKind.RUN_CANCELLATION,
                decision=ApprovalDecision.APPROVED,
                approved_by="test-user",
                approved_at=datetime.now(UTC),
                scope=f"run:{manifest.run_id}:cancel",
            ),
        )

    def _wait_for_terminal(self, idempotency_key: str):
        deadline = time.monotonic() + 8.0
        last = None
        while time.monotonic() < deadline:
            last = self.runner.reconcile(idempotency_key)
            if last.status in (
                RunSubmissionStatus.COMPLETED,
                RunSubmissionStatus.FAILED,
                RunSubmissionStatus.CANCELLED,
            ):
                return last
            time.sleep(0.02)
        self.fail(f"local backend did not reach a terminal state: {last}")


def _artifact_ref(path: Path) -> ArtifactRef:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ArtifactRef(
        artifact_id="local-backend-config",
        uri=path.resolve().as_uri(),
        sha256=digest,
        size_bytes=path.stat().st_size,
    )


def _explicit_test_environment() -> tuple[tuple[str, str], ...]:
    requested = ("SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP")
    values = tuple((name, os.environ[name]) for name in requested if name in os.environ)
    return values + (("PYTHONUTF8", "1"),)


def _write_status(run_root: Path, phase: BackendRunPhase, *, age: float) -> None:
    observed_at = datetime.now(UTC) - timedelta(seconds=age)
    payload = {
        "phase": phase.value,
        "observed_at": observed_at.isoformat(),
        "process_id": os.getpid(),
        "exit_code": None,
        "detail": None,
    }
    (run_root / "status-events" / "00000000000000000001-manual.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _wait_for_path(path: Path) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if path.is_file():
            return
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for {path.name}")


if __name__ == "__main__":
    unittest.main()

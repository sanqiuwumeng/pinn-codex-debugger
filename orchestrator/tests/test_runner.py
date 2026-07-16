from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.contracts import (  # noqa: E402
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
    LogCursor,
    PreparedRun,
    RunCancellationRequest,
    RunManifest,
    RunSubmissionStatus,
)
from pinn_strategy_system.execution import (  # noqa: E402
    IdempotencyConflictError,
    ManifestFirstRunner,
    RunLaunchUncertainError,
    RunPreparationError,
    RunRegistrySchemaError,
    SQLiteRunRegistry,
)

SHA = "2" * 64


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://runner/{name}",
        sha256=SHA,
    )


def manifest(run_id: str = "run-1") -> RunManifest:
    return RunManifest(
        run_id=run_id,
        workflow_id="workflow-1",
        experiment_id="experiment-1",
        idempotency_key="experiment-1-smoke-1",
        environment_name="pytorch2.3.1",
        interpreter="C:/Users/Mli/.conda/envs/pytorch2.3.1/python.exe",
        working_directory="E:/project",
        command=("python", "run.py", "--smoke"),
        config_ref=artifact("staging-config"),
        output_root="artifact://runs/run-1",
        expected_artifacts=("metrics.json", "run_status.json"),
        checkpoint_policy="write before launch and at intervals",
        rollback_plan="Preserve evidence and keep baseline active.",
    )


def approval(workflow_id: str = "workflow-1") -> ApprovalRecord:
    return ApprovalRecord(
        approval_id="approval-1",
        workflow_id=workflow_id,
        kind=ApprovalKind.EXPERIMENT,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=datetime(2026, 7, 15, tzinfo=UTC),
        scope="experiment-1 smoke only",
    )


def cancellation() -> RunCancellationRequest:
    return RunCancellationRequest(
        run_id="run-1",
        workflow_id="workflow-1",
        requested_at=datetime(2026, 7, 16, tzinfo=UTC),
        reason="Operator requested a governed stop.",
        approval=ApprovalRecord(
            approval_id="cancel-approval-1",
            workflow_id="workflow-1",
            kind=ApprovalKind.RUN_CANCELLATION,
            decision=ApprovalDecision.APPROVED,
            approved_by="user",
            approved_at=datetime(2026, 7, 16, tzinfo=UTC),
            scope="run:run-1:cancel",
        ),
    )


class RecordingBackend:
    def __init__(self, registry: SQLiteRunRegistry) -> None:
        self.registry = registry
        self.prepare_count = 0
        self.launch_count = 0
        self.manifest_seen_before_prepare = False
        self.phase = BackendRunPhase.RUNNING

    def prepare(self, request: ExecutionRequest) -> PreparedRun:
        self.prepare_count += 1
        self.manifest_seen_before_prepare = (
            self.registry.lookup(request.manifest.idempotency_key) is not None
        )
        reference = BackendRunRef(
            backend_id="recording",
            run_id=request.manifest.run_id,
            idempotency_key=request.manifest.idempotency_key,
            reference=f"recording://{request.manifest.run_id}",
        )
        return PreparedRun(
            request=request,
            backend_ref=reference,
            staging_root=request.manifest.working_directory,
            prepared_at=datetime.now(UTC),
        )

    def launch(self, prepared_run: PreparedRun) -> BackendRunRef:
        self.launch_count += 1
        return prepared_run.backend_ref

    def reconcile(self, backend_ref: BackendRunRef) -> BackendRunStatus:
        return BackendRunStatus(
            backend_ref=backend_ref,
            phase=self.phase,
            observed_at=datetime.now(UTC),
            exit_code=0 if self.phase is BackendRunPhase.COMPLETED else None,
            log_cursor=LogCursor(
                stdout_offset=128,
                stderr_offset=0,
                observed_at=datetime.now(UTC),
            ),
            checks={"process_identity": True},
        )

    def cancel(
        self,
        backend_ref: BackendRunRef,
        request: RunCancellationRequest,
    ) -> BackendRunStatus:
        self.phase = BackendRunPhase.CANCELLED
        return BackendRunStatus(
            backend_ref=backend_ref,
            phase=self.phase,
            observed_at=datetime.now(UTC),
            checks={"approval": request.approval.decision is ApprovalDecision.APPROVED},
        )

    def collect(
        self,
        backend_ref: BackendRunRef,
        spec: ArtifactCollectionSpec,
    ) -> ArtifactCollectionReport:
        return ArtifactCollectionReport(
            run_id=backend_ref.run_id,
            status=ArtifactCollectionStatus.COMPLETE,
            artifact_refs=(artifact("collected-metrics"),),
            source_manifest_ref=artifact("source-manifest"),
            destination_manifest_ref=artifact("destination-manifest"),
        )


class LostResponseBackend(RecordingBackend):
    def launch(self, prepared_run: PreparedRun) -> BackendRunRef:
        self.launch_count += 1
        raise ConnectionError("launch response was lost")


class FailedPrepareBackend(RecordingBackend):
    def prepare(self, request: ExecutionRequest) -> PreparedRun:
        self.prepare_count += 1
        raise OSError("staging root is unavailable")


class RunnerTests(unittest.TestCase):
    def test_manifest_is_persisted_before_prepare_and_one_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = SQLiteRunRegistry(Path(temp) / "runs.sqlite")
            backend = RecordingBackend(registry)
            runner = ManifestFirstRunner(registry, backend)

            first = runner.submit(manifest(), approval())
            second = runner.submit(manifest(), approval())

            self.assertTrue(backend.manifest_seen_before_prepare)
            self.assertEqual(backend.prepare_count, 1)
            self.assertEqual(backend.launch_count, 1)
            self.assertEqual(first.status, RunSubmissionStatus.RUNNING)
            self.assertFalse(first.duplicate)
            self.assertEqual(second.status, RunSubmissionStatus.RUNNING)
            self.assertTrue(second.duplicate)
            self.assertEqual(second.backend_ref, first.backend_ref)

    def test_lost_launch_response_reconciles_without_relaunch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = SQLiteRunRegistry(Path(temp) / "runs.sqlite")
            backend = LostResponseBackend(registry)
            runner = ManifestFirstRunner(registry, backend)

            with self.assertRaises(RunLaunchUncertainError):
                runner.submit(manifest(), approval())
            retry = runner.submit(manifest(), approval())
            reconciled = runner.reconcile(manifest().idempotency_key)

            self.assertEqual(backend.launch_count, 1)
            self.assertEqual(retry.status, RunSubmissionStatus.RUNNING_UNKNOWN)
            self.assertEqual(reconciled.status, RunSubmissionStatus.RUNNING)
            self.assertTrue(retry.duplicate)

    def test_preparation_failure_is_terminal_without_backend_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = SQLiteRunRegistry(Path(temp) / "runs.sqlite")
            backend = FailedPrepareBackend(registry)

            with self.assertRaises(RunPreparationError):
                ManifestFirstRunner(registry, backend).submit(manifest(), approval())

            stored = registry.lookup(manifest().idempotency_key)
            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertEqual(stored.status, RunSubmissionStatus.FAILED)
            self.assertIsNone(stored.backend_ref)
            self.assertEqual(backend.launch_count, 0)

    def test_completed_run_collects_artifacts_with_two_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = SQLiteRunRegistry(Path(temp) / "runs.sqlite")
            backend = RecordingBackend(registry)
            runner = ManifestFirstRunner(registry, backend)
            running = runner.submit(manifest(), approval())
            backend.phase = BackendRunPhase.COMPLETED
            completed = runner.reconcile(manifest().idempotency_key)
            assert running.backend_ref is not None

            collected = runner.collect(
                manifest().idempotency_key,
                ArtifactCollectionSpec(
                    run_id=manifest().run_id,
                    backend_ref=running.backend_ref,
                    destination_root="E:/artifact-store/run-1",
                    required_artifacts=manifest().expected_artifacts,
                ),
            )

            self.assertEqual(completed.status, RunSubmissionStatus.COMPLETED)
            self.assertEqual(
                completed.last_backend_status.log_cursor.stdout_offset,
                128,
            )
            self.assertEqual(collected.status, RunSubmissionStatus.COMPLETED)
            self.assertEqual(
                collected.collection_report.status,
                ArtifactCollectionStatus.COMPLETE,
            )

    def test_collection_contract_forbids_overwrite(self) -> None:
        reference = BackendRunRef(
            backend_id="recording",
            run_id="run-1",
            idempotency_key="experiment-1-smoke-1",
            reference="recording://run-1",
        )
        with self.assertRaises(ValueError):
            ArtifactCollectionSpec(
                run_id="run-1",
                backend_ref=reference,
                destination_root="E:/artifact-store/run-1",
                required_artifacts=("metrics.json",),
                overwrite_existing=True,
            )

    def test_completed_backend_status_requires_success_evidence(self) -> None:
        reference = BackendRunRef(
            backend_id="recording",
            run_id="run-1",
            idempotency_key="experiment-1-smoke-1",
            reference="recording://run-1",
        )
        with self.assertRaisesRegex(ValueError, "exit_code 0"):
            BackendRunStatus(
                backend_ref=reference,
                phase=BackendRunPhase.COMPLETED,
                observed_at=datetime.now(UTC),
                exit_code=None,
                checks={"process_identity": True},
            )

    def test_cancel_requires_scoped_approval_and_becomes_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = SQLiteRunRegistry(Path(temp) / "runs.sqlite")
            backend = RecordingBackend(registry)
            runner = ManifestFirstRunner(registry, backend)
            runner.submit(manifest(), approval())

            cancelled = runner.cancel(manifest().idempotency_key, cancellation())

            self.assertEqual(cancelled.status, RunSubmissionStatus.CANCELLED)
            self.assertEqual(
                cancelled.last_backend_status.phase,
                BackendRunPhase.CANCELLED,
            )

    def test_same_idempotency_key_cannot_describe_another_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = SQLiteRunRegistry(Path(temp) / "runs.sqlite")
            runner = ManifestFirstRunner(registry, RecordingBackend(registry))
            runner.submit(manifest(), approval())

            with self.assertRaises(IdempotencyConflictError):
                runner.submit(manifest(run_id="different-run"), approval())

    def test_runner_rejects_approval_from_another_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = SQLiteRunRegistry(Path(temp) / "runs.sqlite")
            backend = RecordingBackend(registry)
            runner = ManifestFirstRunner(registry, backend)
            with self.assertRaisesRegex(ValueError, "workflow_id"):
                runner.submit(manifest(), approval("other-workflow"))
            self.assertEqual(backend.prepare_count, 0)
            self.assertEqual(backend.launch_count, 0)

    def test_registry_rejects_legacy_launch_only_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "legacy.sqlite"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("CREATE TABLE run_launches (run_id TEXT)")
                connection.commit()

            with self.assertRaisesRegex(RunRegistrySchemaError, "launch-only"):
                SQLiteRunRegistry(path)


if __name__ == "__main__":
    unittest.main()

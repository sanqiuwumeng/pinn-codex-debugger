from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactRef,
    RunManifest,
    RunSubmissionStatus,
)
from pinn_strategy_system.execution import (  # noqa: E402
    IdempotencyConflictError,
    ManifestFirstRunner,
    RunLaunchUncertainError,
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


class RecordingBackend:
    def __init__(self, registry: SQLiteRunRegistry) -> None:
        self.registry = registry
        self.launch_count = 0
        self.manifest_seen_before_launch = False

    def launch(self, run_manifest: RunManifest) -> str:
        self.launch_count += 1
        self.manifest_seen_before_launch = (
            self.registry.lookup(run_manifest.idempotency_key) is not None
        )
        return "backend://job-1"


class LostResponseBackend:
    def __init__(self) -> None:
        self.launch_count = 0

    def launch(self, run_manifest: RunManifest) -> str:
        self.launch_count += 1
        raise ConnectionError("launch response was lost")


class RunnerTests(unittest.TestCase):
    def test_manifest_is_persisted_before_one_backend_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = SQLiteRunRegistry(Path(temp) / "runs.sqlite")
            backend = RecordingBackend(registry)
            runner = ManifestFirstRunner(registry, backend)

            first = runner.submit(manifest(), approval())
            second = runner.submit(manifest(), approval())

            self.assertTrue(backend.manifest_seen_before_launch)
            self.assertEqual(backend.launch_count, 1)
            self.assertEqual(first.status, RunSubmissionStatus.LAUNCHED)
            self.assertFalse(first.duplicate)
            self.assertEqual(second.status, RunSubmissionStatus.LAUNCHED)
            self.assertTrue(second.duplicate)
            self.assertEqual(second.backend_ref, "backend://job-1")

    def test_lost_launch_response_is_not_relaunched_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = SQLiteRunRegistry(Path(temp) / "runs.sqlite")
            backend = LostResponseBackend()
            runner = ManifestFirstRunner(registry, backend)

            with self.assertRaises(RunLaunchUncertainError):
                runner.submit(manifest(), approval())
            retry = runner.submit(manifest(), approval())

            self.assertEqual(backend.launch_count, 1)
            self.assertEqual(retry.status, RunSubmissionStatus.LAUNCH_UNKNOWN)
            self.assertTrue(retry.duplicate)

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
            self.assertEqual(backend.launch_count, 0)


if __name__ == "__main__":
    unittest.main()

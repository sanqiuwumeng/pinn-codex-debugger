from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.contracts import (  # noqa: E402
    ArtifactRef,
    RunEvent,
    RunEventType,
    RunManifest,
)
from pinn_strategy_system.storage import (  # noqa: E402
    AppendOnlyAuditStore,
    ArtifactConflictError,
    LocalArtifactStore,
    LocalMlflowRunStore,
    SQLiteCheckpointStore,
    StoreLayout,
)

SHA = "8" * 64


def artifact(artifact_id: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        uri=f"artifact://{artifact_id}",
        sha256=SHA,
    )


def manifest() -> RunManifest:
    return RunManifest(
        run_id="run-1",
        workflow_id="workflow-1",
        experiment_id="experiment-1",
        idempotency_key="idem-1",
        environment_name="pytorch2.3.1",
        interpreter="C:/envs/pytorch2.3.1/python.exe",
        working_directory="C:/project",
        command=("python", "smoke.py"),
        config_ref=artifact("config"),
        output_root="artifact://runs/run-1",
        expected_artifacts=("metrics.json",),
        checkpoint_policy="declared milestones",
        rollback_plan="preserve baseline",
    )


class StorageTests(unittest.TestCase):
    def test_layout_assigns_distinct_explicit_owners(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "knowledge"
            knowledge.mkdir()
            layout = StoreLayout.provision(
                runtime_root=root / "runtime",
                knowledge_source_root=knowledge,
            )
            owners = layout.owner_roots()
            self.assertEqual(len(set(owners)), len(owners))
            self.assertTrue(all(path.is_absolute() for path in owners))
            self.assertNotIn(layout.knowledge_source_root, layout.vector_root.parents)
            checkpoint_store = SQLiteCheckpointStore(
                layout.checkpoint_database
            )
            self.assertEqual(
                checkpoint_store.database_path,
                layout.checkpoint_database,
            )

    def test_layout_rejects_runtime_inside_authoritative_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            knowledge = Path(temp)
            with self.assertRaises(ValueError):
                StoreLayout.provision(
                    runtime_root=knowledge / "runtime",
                    knowledge_source_root=knowledge,
                )

    def test_artifacts_are_idempotent_but_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = LocalArtifactStore(root)
            reference = store.put_json("report-1", {"metric": 1.25})
            repeated = store.put_json("report-1", {"metric": 1.25})
            self.assertEqual(reference, repeated)
            with self.assertRaises(ArtifactConflictError):
                store.put_json("report-1", {"metric": 2.0})
            restarted = LocalArtifactStore(root)
            self.assertEqual(
                restarted.read_json(reference),
                {"metric": 1.25},
            )

    def test_audit_events_are_append_only_and_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "audit.sqlite3"
            event = RunEvent(
                event_id="event-1",
                run_id="run-1",
                event_type=RunEventType.RUN_STARTED,
                occurred_at=datetime(2026, 7, 16, tzinfo=UTC),
                payload={"pid": 123},
            )
            store = AppendOnlyAuditStore(database)
            store.append(
                record_id=event.event_id,
                subject_id=event.run_id,
                category="RUN_EVENT",
                occurred_at=event.occurred_at,
                payload=event,
            )
            with self.assertRaises(ValueError):
                store.append(
                    record_id=event.event_id,
                    subject_id=event.run_id,
                    category="RUN_EVENT",
                    occurred_at=event.occurred_at,
                    payload=event,
                )
            restarted = AppendOnlyAuditStore(database)
            records = restarted.records_for("run-1")
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].payload["event_id"], "event-1")

    def test_mlflow_metadata_metrics_and_artifact_refs_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "tracking" / "mlflow.sqlite3"
            database.parent.mkdir()
            artifact_root = root / "artifacts"
            artifact_root.mkdir()
            with LocalMlflowRunStore(
                database_path=database,
                artifact_root=artifact_root,
            ) as store:
                mlflow_run_id = store.record_manifest(manifest())
                store.record_metric(
                    governed_run_id="run-1",
                    name="rmse",
                    value=2.5,
                    timestamp_ms=1_752_614_400_000,
                    step=1,
                )
                store.record_artifact_reference(
                    governed_run_id="run-1",
                    artifact=artifact("metrics"),
                )

            with LocalMlflowRunStore(
                database_path=database,
                artifact_root=artifact_root,
            ) as restarted:
                record = restarted.load("run-1")
            self.assertEqual(record.mlflow_run_id, mlflow_run_id)
            self.assertEqual(record.manifest, manifest())
            self.assertEqual(record.metrics, (("rmse", 2.5),))
            self.assertEqual(
                tuple(item.artifact_id for item in record.artifact_refs),
                ("metrics",),
            )


if __name__ == "__main__":
    unittest.main()

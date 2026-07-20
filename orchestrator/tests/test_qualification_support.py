from __future__ import annotations

import ast
import hashlib
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SRC = REPOSITORY_ROOT / "orchestrator" / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(REPOSITORY_ROOT))

from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactCollectionStatus,
    ArtifactRef,
    MonitorOutcome,
    RunManifest,
)
from pinn_strategy_system.execution import (  # noqa: E402
    LocalProcessRunnerBackend,
    ManifestFirstRunner,
    SQLiteRunRegistry,
)
from pinn_strategy_system.storage import AppendOnlyAuditStore  # noqa: E402
from qualification.support import (  # noqa: E402
    _build_local_backend,
    _local_execution_environment,
    _run_one,
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


FIXTURE = """\
from __future__ import annotations

import json
import sys
from pathlib import Path

output = Path(sys.argv[1])
for relative in (
    "benchmark_config.json",
    "field_metrics.json",
    "closed_loop_validation.json",
    "runtime_environment.json",
    "reproducibility_manifest.json",
):
    path = output / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({}), encoding="utf-8")
for relative in (
    "data/aligned_fields.npz",
    "models/hard_bc_pinn_model.pth",
):
    path = output / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"bounded-adapter-fixture")
print("bounded validation adapter fixture completed")
"""


class QualificationSupportTests(unittest.TestCase):
    def test_portable_qualification_has_no_development_record_dependency(self) -> None:
        paths = (
            REPOSITORY_ROOT / "qualification" / "support.py",
            REPOSITORY_ROOT / "qualification" / "poisson" / "run_poisson_qualification.py",
            REPOSITORY_ROOT / "qualification" / "burgers" / "run_burgers_qualification.py",
        )
        for path in paths:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            calls = tuple(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
            )
            self.assertNotIn("openspec", source.casefold())
            self.assertNotIn("validation/", source.casefold())
            self.assertFalse(
                any(
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"
                    and node.func.attr == "Popen"
                    for node in calls
                )
            )
        support_source = paths[0].read_text(encoding="utf-8")
        self.assertIn("runner.reconcile", support_source)
        self.assertIn("runner.collect", support_source)

    def test_environment_boundary_excludes_credential_names(self) -> None:
        environment = _local_execution_environment()
        names = tuple(name.casefold() for name, _ in environment)
        forbidden_fragments = ("password", "passwd", "token", "secret", "api_key")

        self.assertTrue(environment)
        self.assertEqual(len(names), len(set(names)))
        self.assertFalse(
            any(
                fragment in name
                for name in names
                for fragment in forbidden_fragments
            )
        )

    def test_bounded_adapter_uses_production_reconcile_and_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            run_root = root / "backend-runs"
            run_root.mkdir()
            work_root = root / "work"
            work_root.mkdir()
            fixture = work_root / "fixture.py"
            fixture.write_text(FIXTURE, encoding="utf-8")
            config = work_root / "config.json"
            config.write_text("{}\n", encoding="utf-8")
            output = work_root / "outputs" / "bounded"
            collection = root / "collected" / "bounded-run"
            collection.parent.mkdir()
            backend = _build_local_backend(run_root)
            self.assertIsInstance(backend, LocalProcessRunnerBackend)
            registry = SQLiteRunRegistry(root / "runs.sqlite")
            runner = ManifestFirstRunner(registry, backend)
            manifest = RunManifest(
                run_id="bounded-adapter-run",
                workflow_id="bounded-adapter-workflow",
                experiment_id="bounded-adapter-experiment",
                idempotency_key="bounded-adapter-idempotency",
                environment_name="pinn_strategy_orchestrator-test",
                interpreter=str(Path(sys.executable).resolve()),
                working_directory=str(work_root),
                command=(
                    str(Path(sys.executable).resolve()),
                    str(fixture),
                    str(output),
                ),
                config_ref=_artifact(config),
                output_root=str(output),
                expected_artifacts=EXPECTED_OUTPUTS,
                checkpoint_policy="Bounded adapter fixture only.",
                rollback_plan="Retain bounded adapter evidence.",
            )
            approval = ApprovalRecord(
                approval_id="bounded-adapter-approval",
                workflow_id=manifest.workflow_id,
                kind=ApprovalKind.EXPERIMENT,
                decision=ApprovalDecision.APPROVED,
                approved_by="test-user",
                approved_at=datetime.now(UTC),
                scope="bounded validation adapter test only",
            )

            completed = _run_one(
                manifest=manifest,
                approval=approval,
                runner=runner,
                audit=AppendOnlyAuditStore(root / "audit.sqlite"),
                output_directory=output,
                collection_directory=collection,
                expected_outputs=EXPECTED_OUTPUTS,
            )

            self.assertEqual(completed.exit_code, 0)
            self.assertEqual(
                completed.monitoring["outcome"],
                MonitorOutcome.COMPLETED.value,
            )
            self.assertEqual(
                completed.submission["collection_report"]["status"],
                ArtifactCollectionStatus.COMPLETE.value,
            )
            self.assertTrue((collection / "artifact-manifest.json").is_file())


def _artifact(path: Path) -> ArtifactRef:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ArtifactRef(
        artifact_id="bounded-adapter-config",
        uri=path.resolve().as_uri(),
        sha256=digest,
        size_bytes=path.stat().st_size,
    )


if __name__ == "__main__":
    unittest.main()

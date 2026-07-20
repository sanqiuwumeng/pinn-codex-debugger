from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.application.contracts import OperatorCase  # noqa: E402
from pinn_strategy_system.application.project_adapter import (  # noqa: E402
    ProjectAdapterManifest,
    ProjectAdapterService,
)
from pinn_strategy_system.cli import main  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    ArtifactRef,
    PhysicalModelAuthority,
    SourceRef,
    UnitSystemContract,
    WorkflowRequest,
)

SHA = "a" * 64


def _case(
    project_id: str = "project-adapter",
    *,
    confirmed: bool = True,
) -> OperatorCase:
    source = SourceRef(uri="file:///declared/model.py", sha256=SHA)
    units = UnitSystemContract(
        unit_system_id="declared-units",
        name="User-declared consistent units",
        quantity_units={"u": "dimensionless"},
        source_refs=(source,),
        confirmed_by_user=confirmed,
    )
    model = PhysicalModelAuthority(
        authority_id="declared-model",
        project_id=project_id,
        model_family="PINN",
        pde_family="user-declared-pde",
        task_type="forward",
        governing_equation_refs=(source,),
        output_channels=("u",),
        unit_system=units,
        confirmed_by_user=confirmed,
    )
    request = WorkflowRequest(
        request_id="adapter-request",
        workflow_id="adapter-workflow",
        project_id=project_id,
        objective="Create a governed case without inferring physics.",
        snapshot_ref=ArtifactRef(
            artifact_id="placeholder-snapshot",
            uri="artifact://placeholder/snapshot",
            sha256=SHA,
        ),
        requested_by="user",
    )
    return OperatorCase(
        case_id="adapter-case",
        request=request,
        unit_system=units,
        physical_model=model,
    )


class ProjectAdapterTests(unittest.TestCase):
    def test_adapter_hashes_sorted_sources_and_emits_unresolved_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            (project / "model.py").write_text("equation = 'declared'\n", encoding="utf-8")
            (project / "config.json").write_text(
                '{"unit":"dimensionless"}\n',
                encoding="utf-8",
            )
            service = ProjectAdapterService(artifact_root=root / "artifacts")
            manifest = ProjectAdapterManifest(
                adapter_id="adapter-test",
                project_root=project,
                include_files=(Path("model.py"), Path("config.json")),
                case_template=_case(),
            )

            report = service.adapt(
                manifest=manifest,
                output_path=root / "case.json",
            )

            self.assertEqual(
                tuple(item.relative_path for item in report.files),
                ("config.json", "model.py"),
            )
            self.assertEqual(
                report.case.request.snapshot_ref,
                report.source_snapshot_ref,
            )
            self.assertEqual(
                report.unresolved,
                (
                    "metric_contract",
                    "metric_priority_approval",
                    "baseline_model_evaluation",
                    "experiment_draft",
                ),
            )
            written = OperatorCase.model_validate_json(
                (root / "case.json").read_text(encoding="utf-8")
            )
            self.assertEqual(written, report.case)
            snapshot = json.loads(
                Path(report.source_snapshot_ref.uri.removeprefix("file:///"))
                .read_text(encoding="utf-8")
            )
            self.assertEqual(
                [item["relative_path"] for item in snapshot["files"]],
                ["config.json", "model.py"],
            )

    def test_adapter_rejects_path_escape_before_scanning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with self.assertRaisesRegex(
                ValidationError,
                "confined relative",
            ):
                ProjectAdapterManifest(
                    adapter_id="adapter-escape",
                    project_root=root,
                    include_files=(Path("../secret.txt"),),
                    case_template=_case(),
                )

    def test_ambiguous_physics_remains_explicitly_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            (project / "model.py").write_text("model = 1\n", encoding="utf-8")
            report = ProjectAdapterService(
                artifact_root=root / "artifacts"
            ).adapt(
                manifest=ProjectAdapterManifest(
                    adapter_id="adapter-ambiguous-physics",
                    project_root=project,
                    include_files=(Path("model.py"),),
                    case_template=_case(confirmed=False),
                ),
                output_path=root / "case.json",
            )

            self.assertIn("unit_system_confirmation", report.unresolved)
            self.assertIn("physical_model_confirmation", report.unresolved)

    def test_adapter_never_overwrites_an_existing_case(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            (project / "model.py").write_text("model = 1\n", encoding="utf-8")
            target = root / "case.json"
            target.write_text("preserve me", encoding="utf-8")
            service = ProjectAdapterService(artifact_root=root / "artifacts")
            manifest = ProjectAdapterManifest(
                adapter_id="adapter-no-overwrite",
                project_root=project,
                include_files=(Path("model.py"),),
                case_template=_case(),
            )

            with self.assertRaises(FileExistsError):
                service.adapt(manifest=manifest, output_path=target)
            self.assertEqual(target.read_text(encoding="utf-8"), "preserve me")

    def test_cli_adapt_surfaces_unresolved_user_governed_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            (project / "model.py").write_text("model = 1\n", encoding="utf-8")
            manifest = ProjectAdapterManifest(
                adapter_id="adapter-cli",
                project_root=project,
                include_files=(Path("model.py"),),
                case_template=_case(),
            )
            manifest_path = root / "adapter.json"
            manifest_path.write_text(
                manifest.model_dump_json(indent=2),
                encoding="utf-8",
            )
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(
                    [
                        "adapt",
                        "--runtime-root",
                        str(root / "runtime"),
                        "--manifest",
                        str(manifest_path),
                        "--output",
                        str(root / "case.json"),
                        "--json",
                    ]
                )
            payload = json.loads(stream.getvalue())

            self.assertEqual(code, 2)
            self.assertEqual(payload["code"], "ADAPTED_WITH_UNRESOLVED")
            self.assertIn("metric_contract", payload["data"]["unresolved"])
            self.assertTrue((root / "case.json").is_file())


if __name__ == "__main__":
    unittest.main()

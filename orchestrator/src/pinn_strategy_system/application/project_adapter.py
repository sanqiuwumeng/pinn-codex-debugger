"""Manifest-driven onboarding for existing PINN projects."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from pinn_strategy_system.contracts import (
    ApprovalDecision,
    ApprovalKind,
    ArtifactRef,
    VersionedModel,
    WorkflowIntent,
)
from pinn_strategy_system.storage import LocalArtifactStore

from .contracts import OperatorCase


class ProjectAdapterManifest(VersionedModel):
    """Explicit project boundary plus an operator-owned case template."""

    adapter_id: str = Field(min_length=1, max_length=256)
    project_root: Path
    include_files: tuple[Path, ...] = Field(min_length=1)
    case_template: OperatorCase

    @model_validator(mode="after")
    def paths_and_project_match(self) -> Self:
        if not self.project_root.is_absolute():
            raise ValueError("project_root must be absolute")
        invalid = tuple(
            path
            for path in self.include_files
            if path.is_absolute()
            or path in {Path("."), Path("..")}
            or ".." in path.parts
        )
        if invalid:
            raise ValueError(
                "include_files must contain confined relative file paths"
            )
        normalized = tuple(path.as_posix().casefold() for path in self.include_files)
        if len(set(normalized)) != len(normalized):
            raise ValueError("include_files must not contain duplicate paths")
        if (
            self.case_template.request.project_id
            != self.case_template.physical_model.project_id
        ):
            raise ValueError("case template project identifiers must match")
        return self


class SourceFileRecord(VersionedModel):
    relative_path: str = Field(min_length=1, max_length=4096)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProjectAdaptationReport(VersionedModel):
    adapter_id: str = Field(min_length=1, max_length=256)
    case: OperatorCase
    source_snapshot_ref: ArtifactRef
    files: tuple[SourceFileRecord, ...]
    unresolved: tuple[str, ...] = ()
    output_path: Path

    @model_validator(mode="after")
    def output_is_absolute(self) -> Self:
        if not self.output_path.is_absolute():
            raise ValueError("output_path must be absolute")
        return self


class ProjectAdapterService:
    """Create one governed case without inferring domain semantics."""

    def __init__(self, *, artifact_root: Path) -> None:
        if not artifact_root.is_absolute():
            raise ValueError("artifact_root must be absolute")
        artifact_root.mkdir(parents=True, exist_ok=True)
        self._artifacts = LocalArtifactStore(artifact_root)

    def adapt(
        self,
        *,
        manifest: ProjectAdapterManifest,
        output_path: Path,
    ) -> ProjectAdaptationReport:
        root = manifest.project_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("project_root must be an existing directory")
        if not output_path.is_absolute():
            raise ValueError("output path must be absolute")
        target = output_path.resolve(strict=False)
        if not target.parent.is_dir():
            raise ValueError("output path parent must be an existing absolute directory")
        if target.exists():
            raise FileExistsError("operator case output already exists")

        records = tuple(
            sorted(
                (self._inspect_file(root, item) for item in manifest.include_files),
                key=lambda item: item.relative_path,
            )
        )
        snapshot_payload = {
            "schema_version": "1.0",
            "adapter_id": manifest.adapter_id,
            "project_id": manifest.case_template.request.project_id,
            "project_root_uri": root.as_uri(),
            "files": [item.model_dump(mode="json") for item in records],
        }
        snapshot_digest = _canonical_digest(snapshot_payload)
        snapshot_ref = self._artifacts.put_json(
            f"source-snapshot-{snapshot_digest[:24]}",
            snapshot_payload,
        )
        case = _case_with_snapshot(manifest.case_template, snapshot_ref)
        unresolved = _unresolved_contracts(case)
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(case.model_dump_json(indent=2))
            stream.write("\n")
        return ProjectAdaptationReport(
            adapter_id=manifest.adapter_id,
            case=case,
            source_snapshot_ref=snapshot_ref,
            files=records,
            unresolved=unresolved,
            output_path=target,
        )

    @staticmethod
    def _inspect_file(root: Path, relative_path: Path) -> SourceFileRecord:
        candidate = (root / relative_path).resolve(strict=True)
        try:
            normalized = candidate.relative_to(root)
        except ValueError as error:
            raise ValueError("declared source path escapes project_root") from error
        if not candidate.is_file():
            raise ValueError("every declared source path must be a regular file")
        return SourceFileRecord(
            relative_path=normalized.as_posix(),
            size_bytes=candidate.stat().st_size,
            sha256=_file_sha256(candidate),
        )


def _case_with_snapshot(
    case: OperatorCase,
    snapshot_ref: ArtifactRef,
) -> OperatorCase:
    request = case.request.model_copy(update={"snapshot_ref": snapshot_ref})
    experiment = case.experiment_draft
    if experiment is not None:
        experiment = experiment.model_copy(
            update={"source_snapshot_ref": snapshot_ref}
        )
    payload = case.model_dump(mode="python")
    payload.update({"request": request, "experiment_draft": experiment})
    return OperatorCase.model_validate(payload)


def _unresolved_contracts(case: OperatorCase) -> tuple[str, ...]:
    approved_kinds = {
        item.kind
        for item in case.approvals
        if item.decision is ApprovalDecision.APPROVED
    }
    checks = (
        (not case.unit_system.confirmed_by_user, "unit_system_confirmation"),
        (not case.physical_model.confirmed_by_user, "physical_model_confirmation"),
        (case.metric_contract is None, "metric_contract"),
        (
            ApprovalKind.METRIC_PRIORITY not in approved_kinds,
            "metric_priority_approval",
        ),
        (case.model_evaluation is None, "baseline_model_evaluation"),
        (case.experiment_draft is None, "experiment_draft"),
        (
            case.request.intent is WorkflowIntent.SMOKE
            and case.smoke_manifest is None,
            "smoke_manifest",
        ),
        (
            case.request.intent is WorkflowIntent.FULL_RUN
            and case.full_manifest is None,
            "full_manifest",
        ),
        (
            case.request.intent in {WorkflowIntent.SMOKE, WorkflowIntent.FULL_RUN}
            and case.execution_profile_path is None,
            "execution_profile_path",
        ),
    )
    return tuple(label for missing, label in checks if missing)


def _canonical_digest(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

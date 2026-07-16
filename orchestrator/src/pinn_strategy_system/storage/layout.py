"""Validated path ownership for every development persistence concern."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoreLayout:
    runtime_root: Path
    checkpoint_database: Path
    tracking_database: Path
    artifact_root: Path
    vector_root: Path
    audit_database: Path
    knowledge_source_root: Path

    @classmethod
    def provision(
        cls,
        *,
        runtime_root: str | Path,
        knowledge_source_root: str | Path,
    ) -> "StoreLayout":
        runtime = _absolute_path(runtime_root, "runtime_root")
        knowledge = _absolute_path(
            knowledge_source_root,
            "knowledge_source_root",
        )
        if not knowledge.exists() or not knowledge.is_dir():
            raise ValueError("knowledge_source_root must be an existing directory")
        if _overlaps(runtime, knowledge):
            raise ValueError(
                "runtime stores and authoritative knowledge must not overlap"
            )

        runtime.mkdir(parents=True, exist_ok=True)
        checkpoint_root = runtime / "workflow_checkpoints"
        tracking_root = runtime / "run_tracking"
        artifact_root = runtime / "artifacts"
        vector_root = runtime / "vector_index"
        audit_root = runtime / "audit_events"
        owner_roots = (
            checkpoint_root,
            tracking_root,
            artifact_root,
            vector_root,
            audit_root,
            knowledge,
        )
        _assert_isolated(owner_roots)
        for owner_root in owner_roots[:-1]:
            owner_root.mkdir(parents=True, exist_ok=True)

        return cls(
            runtime_root=runtime,
            checkpoint_database=checkpoint_root / "workflow.sqlite3",
            tracking_database=tracking_root / "mlflow.sqlite3",
            artifact_root=artifact_root,
            vector_root=vector_root,
            audit_database=audit_root / "events.sqlite3",
            knowledge_source_root=knowledge,
        )

    def owner_roots(self) -> tuple[Path, ...]:
        return (
            self.checkpoint_database.parent,
            self.tracking_database.parent,
            self.artifact_root,
            self.vector_root,
            self.audit_database.parent,
            self.knowledge_source_root,
        )


def _absolute_path(value: str | Path, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute")
    return path.resolve(strict=False)


def _assert_isolated(paths: tuple[Path, ...]) -> None:
    for index, left in enumerate(paths):
        for right in paths[index + 1 :]:
            if _overlaps(left, right):
                raise ValueError(
                    f"store ownership paths overlap: {left} and {right}"
                )


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents

"""MLflow-backed local run metadata with artifact references only."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Self

from mlflow import MlflowClient

from pinn_strategy_system.contracts import ArtifactRef, RunManifest

RUN_ID_TAG = "pinn_strategy.governed_run_id"
MANIFEST_TAG = "pinn_strategy.run_manifest"
ARTIFACT_TAG_PREFIX = "pinn_strategy.artifact."


@dataclass(frozen=True)
class StoredRunRecord:
    mlflow_run_id: str
    manifest: RunManifest
    metrics: tuple[tuple[str, float], ...]
    artifact_refs: tuple[ArtifactRef, ...]


class LocalMlflowRunStore:
    def __init__(
        self,
        *,
        database_path: str | Path,
        artifact_root: str | Path,
        experiment_name: str = "pinn-strategy-development",
    ) -> None:
        database = _existing_parent_absolute(database_path, "tracking database")
        artifacts = Path(artifact_root)
        if not artifacts.is_absolute():
            raise ValueError("MLflow artifact root must be absolute")
        if not artifacts.exists() or not artifacts.is_dir():
            raise ValueError("MLflow artifact root must be an existing directory")
        self._client = MlflowClient(
            tracking_uri=f"sqlite:///{database.as_posix()}"
        )
        self._closed = False
        self._experiment_id = self._ensure_experiment(
            experiment_name,
            artifacts.resolve(strict=False).as_uri(),
        )

    def __enter__(self) -> Self:
        if self._closed:
            raise RuntimeError("MLflow run store is closed")
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        tracking_store = self._client._tracking_client.store
        dispose_engine = getattr(tracking_store, "_dispose_engine", None)
        if not callable(dispose_engine):
            raise RuntimeError(
                "pinned MLflow tracking store exposes no engine disposer"
            )
        dispose_engine()
        self._closed = True

    def record_manifest(self, manifest: RunManifest) -> str:
        self._ensure_open()
        serialized = manifest.model_dump_json()
        existing = self._find(manifest.run_id)
        if existing is not None:
            if existing.data.tags.get(MANIFEST_TAG) != serialized:
                raise ValueError(
                    "governed run_id already has a different RunManifest"
                )
            return existing.info.run_id
        created = self._client.create_run(
            self._experiment_id,
            tags={
                RUN_ID_TAG: manifest.run_id,
                MANIFEST_TAG: serialized,
            },
        )
        return created.info.run_id

    def record_metric(
        self,
        *,
        governed_run_id: str,
        name: str,
        value: float,
        timestamp_ms: int,
        step: int,
    ) -> None:
        self._ensure_open()
        if not math.isfinite(value):
            raise ValueError("MLflow metric must be finite")
        run = self._require(governed_run_id)
        self._client.log_metric(
            run.info.run_id,
            name,
            value,
            timestamp_ms,
            step,
        )

    def record_artifact_reference(
        self,
        *,
        governed_run_id: str,
        artifact: ArtifactRef,
    ) -> None:
        self._ensure_open()
        run = self._require(governed_run_id)
        self._client.set_tag(
            run.info.run_id,
            f"{ARTIFACT_TAG_PREFIX}{artifact.artifact_id}",
            artifact.model_dump_json(),
        )

    def load(self, governed_run_id: str) -> StoredRunRecord:
        self._ensure_open()
        run = self._require(governed_run_id)
        manifest_json = run.data.tags.get(MANIFEST_TAG)
        if manifest_json is None:
            raise RuntimeError("tracked run is missing its RunManifest")
        artifacts = tuple(
            ArtifactRef.model_validate_json(value)
            for key, value in sorted(run.data.tags.items())
            if key.startswith(ARTIFACT_TAG_PREFIX)
        )
        return StoredRunRecord(
            mlflow_run_id=run.info.run_id,
            manifest=RunManifest.model_validate_json(manifest_json),
            metrics=tuple(sorted(run.data.metrics.items())),
            artifact_refs=artifacts,
        )

    def _ensure_experiment(
        self,
        experiment_name: str,
        artifact_location: str,
    ) -> str:
        existing = self._client.get_experiment_by_name(experiment_name)
        if existing is not None:
            if existing.artifact_location != artifact_location:
                raise ValueError(
                    "MLflow experiment already owns another artifact root"
                )
            return existing.experiment_id
        return self._client.create_experiment(
            experiment_name,
            artifact_location=artifact_location,
        )

    def _find(self, governed_run_id: str):
        matches = tuple(
            run
            for run in self._client.search_runs(
                experiment_ids=(self._experiment_id,),
                max_results=5000,
            )
            if run.data.tags.get(RUN_ID_TAG) == governed_run_id
        )
        if len(matches) > 1:
            raise RuntimeError(
                f"multiple MLflow runs map to governed run_id {governed_run_id}"
            )
        return matches[0] if matches else None

    def _require(self, governed_run_id: str):
        run = self._find(governed_run_id)
        if run is None:
            raise KeyError(f"unknown governed run_id: {governed_run_id}")
        return run

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("MLflow run store is closed")


def _existing_parent_absolute(value: str | Path, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{label} path must be absolute")
    if not path.parent.exists():
        raise ValueError(f"{label} parent directory must already exist")
    return path.resolve(strict=False)

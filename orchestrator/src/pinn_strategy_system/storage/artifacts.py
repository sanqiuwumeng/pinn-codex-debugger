"""Content-addressed JSON artifacts with no-overwrite semantics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pinn_strategy_system.contracts import ArtifactRef


class ArtifactConflictError(RuntimeError):
    pass


class LocalArtifactStore:
    def __init__(self, root: str | Path) -> None:
        path = Path(root)
        if not path.is_absolute():
            raise ValueError("artifact root must be absolute")
        if not path.exists() or not path.is_dir():
            raise ValueError("artifact root must be an existing directory")
        self._root = path.resolve(strict=False)

    def put_json(self, artifact_id: str, payload: Any) -> ArtifactRef:
        target = self._target(artifact_id)
        content = _canonical_json_bytes(payload)
        digest = hashlib.sha256(content).hexdigest()
        try:
            with target.open("xb") as stream:
                stream.write(content)
                stream.flush()
        except FileExistsError as error:
            if target.read_bytes() != content:
                raise ArtifactConflictError(
                    f"artifact_id already exists with different content: {artifact_id}"
                ) from error
        return ArtifactRef(
            artifact_id=artifact_id,
            uri=target.as_uri(),
            sha256=digest,
            media_type="application/json",
            size_bytes=len(content),
        )

    def read_json(self, artifact: ArtifactRef) -> Any:
        target = self._target(artifact.artifact_id)
        if target.as_uri() != artifact.uri:
            raise ValueError("artifact URI does not belong to this store")
        content = target.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != artifact.sha256:
            raise RuntimeError("artifact content hash does not match its reference")
        return json.loads(content.decode("utf-8"))

    def _target(self, artifact_id: str) -> Path:
        if (
            not artifact_id
            or Path(artifact_id).name != artifact_id
            or artifact_id in {".", ".."}
        ):
            raise ValueError("artifact_id must be one safe path segment")
        return self._root / f"{artifact_id}.json"


def _canonical_json_bytes(payload: Any) -> bytes:
    try:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"artifact payload must be strict JSON: {error}") from error
    return serialized.encode("utf-8")

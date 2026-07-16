"""Content-addressed Qdrant build, canary, activation and rollback."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import Field

from pinn_strategy_system.contracts import (
    ChunkMetadata,
    ChunkingPolicy,
    VersionedModel,
)

from .models import RetrievalScope
from .source import FilesystemKnowledgeSource
from .vector_index import EmbeddingProvider, LocalQdrantIndex


class IdentifiedEmbeddingProvider(EmbeddingProvider, Protocol):
    @property
    def provenance_identity(self) -> tuple[str, str, int]: ...


class IndexIdentity(VersionedModel):
    identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    collection_name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    embedding_model_id: str = Field(min_length=1, max_length=512)
    embedding_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    vector_size: int = Field(ge=1, le=65_536)
    chunking_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class IndexBuildReport(VersionedModel):
    identity: IndexIdentity
    document_count: int = Field(ge=1)
    reused_existing_collection: bool


class IndexCanaryReport(VersionedModel):
    identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hit_ids: tuple[str, ...] = ()
    minimum_hits: int = Field(ge=1)
    required_hit_ids: tuple[str, ...] = ()
    passed: bool


class IndexActivationRecord(VersionedModel):
    active: IndexIdentity
    previous: IndexIdentity | None = None
    activated_at: datetime
    canary: IndexCanaryReport


class QdrantIndexGovernance:
    def __init__(
        self,
        *,
        qdrant_root: Path,
        state_root: Path,
    ) -> None:
        for label, path in (
            ("Qdrant root", qdrant_root),
            ("index state root", state_root),
        ):
            if not path.is_absolute() or not path.is_dir():
                raise ValueError(f"{label} must be an existing absolute directory")
        self._qdrant_root = qdrant_root.resolve(strict=False)
        self._state_root = state_root.resolve(strict=False)
        self._active_path = self._state_root / "active-index.json"

    def identity(
        self,
        *,
        source: FilesystemKnowledgeSource,
        embedder: IdentifiedEmbeddingProvider,
        chunking_policy: ChunkingPolicy,
    ) -> IndexIdentity:
        documents = source.load_documents()
        if not documents:
            raise ValueError("cannot identify an empty knowledge source")
        model_id, revision, vector_size = embedder.provenance_identity
        chunking_sha = _canonical_sha(chunking_policy.model_dump(mode="json"))
        metadata_sha = _canonical_sha(ChunkMetadata.model_json_schema())
        source_sha = _canonical_sha(
            tuple(
                {
                    "chunk_id": item.chunk.chunk_id,
                    "chunk_sha256": item.chunk.chunk_sha256,
                    "metadata": item.chunk.metadata.model_dump(mode="json"),
                    "applicable_versions": item.applicable_versions,
                    "claims": tuple(
                        claim.model_dump(mode="json") for claim in item.claims
                    ),
                }
                for item in documents
            )
        )
        identity_payload = {
            "embedding_model_id": model_id,
            "embedding_revision": revision,
            "vector_size": vector_size,
            "chunking_policy_sha256": chunking_sha,
            "metadata_schema_sha256": metadata_sha,
            "source_identity_sha256": source_sha,
        }
        identity_sha = _canonical_sha(identity_payload)
        return IndexIdentity(
            identity_sha256=identity_sha,
            collection_name=f"pinn-knowledge-{identity_sha[:24]}",
            **identity_payload,
        )

    def build_candidate(
        self,
        *,
        source: FilesystemKnowledgeSource,
        embedder: IdentifiedEmbeddingProvider,
        chunking_policy: ChunkingPolicy,
    ) -> IndexBuildReport:
        identity = self.identity(
            source=source,
            embedder=embedder,
            chunking_policy=chunking_policy,
        )
        expected_count = len(source.load_documents())
        with LocalQdrantIndex(
            root=self._qdrant_root,
            collection_name=identity.collection_name,
            vector_size=identity.vector_size,
        ) as index:
            observed = index.count()
            reused = observed > 0
            if reused and observed != expected_count:
                raise RuntimeError(
                    "content-addressed Qdrant collection count is inconsistent"
                )
            if not reused:
                observed = index.rebuild(source=source, embedder=embedder)
        return IndexBuildReport(
            identity=identity,
            document_count=observed,
            reused_existing_collection=reused,
        )

    def canary(
        self,
        *,
        build: IndexBuildReport,
        query: str,
        scope: RetrievalScope,
        embedder: IdentifiedEmbeddingProvider,
        minimum_hits: int = 1,
        required_hit_ids: tuple[str, ...] = (),
    ) -> IndexCanaryReport:
        if minimum_hits < 1:
            raise ValueError("index canary minimum_hits must be positive")
        if embedder.provenance_identity != (
            build.identity.embedding_model_id,
            build.identity.embedding_revision,
            build.identity.vector_size,
        ):
            raise ValueError("index canary embedder identity mismatch")
        with LocalQdrantIndex(
            root=self._qdrant_root,
            collection_name=build.identity.collection_name,
            vector_size=build.identity.vector_size,
        ) as index:
            hits = index.search(
                query_vector=embedder.embed_query(query),
                scope=scope,
                limit=max(minimum_hits, len(required_hit_ids), 1),
            )
        hit_ids = tuple(item.document.chunk.chunk_id for item in hits)
        passed = (
            len(hit_ids) >= minimum_hits
            and set(required_hit_ids).issubset(hit_ids)
        )
        return IndexCanaryReport(
            identity_sha256=build.identity.identity_sha256,
            query_sha256=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            hit_ids=hit_ids,
            minimum_hits=minimum_hits,
            required_hit_ids=required_hit_ids,
            passed=passed,
        )

    def activate(
        self,
        *,
        build: IndexBuildReport,
        canary: IndexCanaryReport,
    ) -> IndexActivationRecord:
        if not canary.passed:
            raise ValueError("failed index canary cannot be activated")
        if canary.identity_sha256 != build.identity.identity_sha256:
            raise ValueError("index build and canary identity mismatch")
        previous_record = self.active()
        record = IndexActivationRecord(
            active=build.identity,
            previous=(
                previous_record.active if previous_record is not None else None
            ),
            activated_at=datetime.now(UTC),
            canary=canary,
        )
        self._write_activation(record)
        return record

    def rollback(self) -> IndexActivationRecord:
        current = self.active()
        if current is None or current.previous is None:
            raise RuntimeError("no previous Qdrant index is available for rollback")
        with LocalQdrantIndex(
            root=self._qdrant_root,
            collection_name=current.previous.collection_name,
            vector_size=current.previous.vector_size,
        ) as index:
            if index.count() < 1:
                raise RuntimeError("previous Qdrant collection is unavailable")
        rollback_canary = self._activation_canary(current.previous)
        record = IndexActivationRecord(
            active=current.previous,
            previous=current.active,
            activated_at=datetime.now(UTC),
            canary=rollback_canary,
        )
        self._write_activation(record)
        return record

    def _activation_canary(self, identity: IndexIdentity) -> IndexCanaryReport:
        history_root = self._state_root / "activation-history"
        for path in sorted(history_root.glob("*.json"), reverse=True):
            historical = IndexActivationRecord.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            if historical.active.identity_sha256 == identity.identity_sha256:
                return historical.canary
        raise RuntimeError("previous Qdrant index has no activation canary")

    def active(self) -> IndexActivationRecord | None:
        if not self._active_path.exists():
            return None
        return IndexActivationRecord.model_validate_json(
            self._active_path.read_text(encoding="utf-8")
        )

    def open_active(self) -> LocalQdrantIndex:
        record = self.active()
        if record is None:
            raise RuntimeError("no active Qdrant index is configured")
        return LocalQdrantIndex(
            root=self._qdrant_root,
            collection_name=record.active.collection_name,
            vector_size=record.active.vector_size,
        )

    def _write_activation(self, record: IndexActivationRecord) -> None:
        now = datetime.now(UTC)
        if self._active_path.exists():
            backup_root = self._state_root / "activation-backups" / (
                now.strftime("%Y%m%d_%H%M%S_%f")
            )
            backup_root.mkdir(parents=True, exist_ok=False)
            shutil.copy2(
                self._active_path,
                backup_root
                / f"active-index.json_backup_{now.strftime('%Y-%m-%d')}",
            )
        history_root = self._state_root / "activation-history"
        history_root.mkdir(parents=True, exist_ok=True)
        encoded = record.model_dump_json(indent=2) + "\n"
        history_path = history_root / (
            f"activation-{now.strftime('%Y%m%dT%H%M%S_%fZ')}-{uuid.uuid4().hex}.json"
        )
        history_path.write_text(encoded, encoding="utf-8")
        temporary = self._state_root / f".active-index-{uuid.uuid4().hex}.tmp"
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, self._active_path)


def _canonical_sha(value) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

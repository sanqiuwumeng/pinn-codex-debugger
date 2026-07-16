"""Qdrant local-mode derived index with explicit rebuild semantics."""

from __future__ import annotations

import math
import uuid
from pathlib import Path
from types import TracebackType
from typing import Protocol, Self

from qdrant_client import QdrantClient, models

from .models import (
    IndexedKnowledgeDocument,
    RetrievalScope,
    VectorHit,
)
from .provenance import ProvenanceValidator
from .source import FilesystemKnowledgeSource


class EmbeddingProvider(Protocol):
    def embed_documents(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]: ...

    def embed_query(self, text: str) -> tuple[float, ...]: ...


class LocalQdrantIndex:
    def __init__(
        self,
        *,
        root: str | Path,
        collection_name: str,
        vector_size: int,
    ) -> None:
        path = Path(root)
        if not path.is_absolute():
            raise ValueError("Qdrant local root must be absolute")
        if not path.exists() or not path.is_dir():
            raise ValueError("Qdrant local root must be an existing directory")
        if vector_size < 1:
            raise ValueError("vector_size must be positive")
        self._client = QdrantClient(path=str(path.resolve(strict=False)))
        self._collection_name = collection_name
        self._vector_size = vector_size
        self._closed = False
        self._provenance = ProvenanceValidator()

    @property
    def collection_name(self) -> str:
        return self._collection_name

    @property
    def vector_size(self) -> int:
        return self._vector_size

    def __enter__(self) -> Self:
        self._ensure_open()
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
        self._client.close()
        self._closed = True

    def rebuild(
        self,
        *,
        source: FilesystemKnowledgeSource,
        embedder: EmbeddingProvider,
    ) -> int:
        self._ensure_open()
        documents = source.load_documents()
        if not documents:
            raise ValueError("cannot build a vector index from an empty source")
        for document in documents:
            self._provenance.require(document)
        vectors = embedder.embed_documents(
            tuple(document.chunk.text for document in documents)
        )
        validated = _validated_vectors(
            vectors,
            expected_count=len(documents),
            vector_size=self._vector_size,
        )
        points = tuple(
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, document.chunk.chunk_id)),
                vector=list(vector),
                payload=_payload(document),
            )
            for document, vector in zip(documents, validated, strict=True)
        )

        if self._client.collection_exists(self._collection_name):
            self._delete_collection()
        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config=models.VectorParams(
                size=self._vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        self._client.upsert(
            collection_name=self._collection_name,
            points=list(points),
            wait=True,
        )
        return len(points)

    def search(
        self,
        *,
        query_vector: tuple[float, ...],
        scope: RetrievalScope,
        limit: int,
    ) -> tuple[VectorHit, ...]:
        self._ensure_open()
        vector = _validated_vectors(
            (query_vector,),
            expected_count=1,
            vector_size=self._vector_size,
        )[0]
        if limit < 1:
            raise ValueError("vector search limit must be positive")
        if not self._client.collection_exists(self._collection_name):
            return ()
        response = self._client.query_points(
            collection_name=self._collection_name,
            query=list(vector),
            query_filter=_scope_filter(scope),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        hits: list[VectorHit] = []
        for point in response.points:
            payload = point.payload
            if not isinstance(payload, dict) or "document" not in payload:
                raise RuntimeError("Qdrant point is missing its source document")
            document = IndexedKnowledgeDocument.model_validate(
                payload["document"]
            )
            self._provenance.require(document)
            hits.append(
                VectorHit(
                    document=document,
                    score=float(point.score),
                )
            )
        return tuple(hits)

    def delete_collection(self) -> bool:
        self._ensure_open()
        if not self._client.collection_exists(self._collection_name):
            return False
        return self._delete_collection()

    def count(self) -> int:
        self._ensure_open()
        if not self._client.collection_exists(self._collection_name):
            return 0
        return int(
            self._client.count(
                collection_name=self._collection_name,
                exact=True,
            ).count
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Qdrant index is closed")

    def _delete_collection(self) -> bool:
        local_backend = getattr(self._client, "_client", None)
        collections = getattr(local_backend, "collections", None)
        if not isinstance(collections, dict):
            raise RuntimeError(
                "pinned Qdrant local backend exposes no collection registry"
            )
        collection = collections.get(self._collection_name)
        if collection is not None:
            collection.close()
        return self._client.delete_collection(self._collection_name)


def _validated_vectors(
    vectors: tuple[tuple[float, ...], ...],
    *,
    expected_count: int,
    vector_size: int,
) -> tuple[tuple[float, ...], ...]:
    if len(vectors) != expected_count:
        raise ValueError("embedding provider returned the wrong vector count")
    normalized = tuple(tuple(float(value) for value in vector) for vector in vectors)
    if any(len(vector) != vector_size for vector in normalized):
        raise ValueError("embedding provider returned the wrong vector size")
    if any(
        not math.isfinite(value)
        for vector in normalized
        for value in vector
    ):
        raise ValueError("embedding provider returned a non-finite value")
    return normalized


def _payload(document: IndexedKnowledgeDocument) -> dict:
    metadata = document.chunk.metadata
    return {
        "project_id": metadata.project_id,
        "document_type": metadata.document_type,
        "validation_status": metadata.validation_status,
        "model_family": metadata.model_family,
        "pde_family": metadata.pde_family,
        "task_type": metadata.task_type,
        "domain_provider_id": metadata.domain_provider_id,
        "output_channels": list(metadata.output_channels),
        "dimensional_signatures": list(metadata.dimensional_signatures),
        "failure_signatures": list(metadata.failure_signatures),
        "framework": metadata.framework,
        "language": metadata.language,
        "applicable_versions": list(document.applicable_versions),
        "document": document.model_dump(mode="json"),
    }


def _scope_filter(scope: RetrievalScope) -> models.Filter:
    conditions: list[models.FieldCondition] = [
        models.FieldCondition(
            key="project_id",
            match=models.MatchValue(value=scope.project_id),
        )
    ]
    optional_any = (
        ("document_type", scope.document_types),
        ("validation_status", scope.validation_statuses),
        ("language", scope.languages),
        ("output_channels", scope.output_channels),
        ("dimensional_signatures", scope.dimensional_signatures),
        ("failure_signatures", scope.failure_signatures),
    )
    conditions.extend(
        models.FieldCondition(
            key=key,
            match=models.MatchAny(any=list(values)),
        )
        for key, values in optional_any
        if values
    )
    optional_exact = (
        ("model_family", scope.model_family),
        ("pde_family", scope.pde_family),
        ("task_type", scope.task_type),
        ("domain_provider_id", scope.domain_provider_id),
        ("framework", scope.framework),
        ("applicable_versions", scope.applicable_version),
    )
    conditions.extend(
        models.FieldCondition(
            key=key,
            match=models.MatchValue(value=value),
        )
        for key, value in optional_exact
        if value is not None
    )
    return models.Filter(must=conditions)

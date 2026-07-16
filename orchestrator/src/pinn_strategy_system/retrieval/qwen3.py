"""Pinned Qwen3 embedding and reranking providers."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol

from .model_runtime import (
    EmbeddingRequest,
    EmbeddingResponse,
    ModelProvenance,
    ModelTransport,
    RerankDocument,
    RerankRequest,
    RerankResponse,
)
from .models import HybridEvidence, RerankedEvidence


QWEN3_EMBEDDING_MODEL_ID = "Qwen/Qwen3-Embedding-8B"
QWEN3_EMBEDDING_REVISION = "1d8ad4ca9b3dd8059ad90a75d4983776a23d44af"
QWEN3_RERANKER_MODEL_ID = "Qwen/Qwen3-Reranker-4B"
QWEN3_RERANKER_REVISION = "22e683669bc0f0bd69640a1354a6d0aebcfeede5"
QWEN3_EMBEDDING_DIMENSION = 4096


class RerankingProvider(Protocol):
    def rerank(
        self,
        *,
        query: str,
        evidence: tuple[HybridEvidence, ...],
    ) -> tuple[RerankedEvidence, ...]: ...


class Qwen3EmbeddingProvider:
    def __init__(
        self,
        *,
        transport: ModelTransport,
        request_id_factory: Callable[[str], str] | None = None,
        output_dimension: int = QWEN3_EMBEDDING_DIMENSION,
    ) -> None:
        if output_dimension != QWEN3_EMBEDDING_DIMENSION:
            raise ValueError("production Qwen3 embedding dimension must be 4096")
        self._transport = transport
        self._request_id_factory = request_id_factory
        self._output_dimension = output_dimension

    @property
    def provenance_identity(self) -> tuple[str, str, int]:
        return (
            QWEN3_EMBEDDING_MODEL_ID,
            QWEN3_EMBEDDING_REVISION,
            self._output_dimension,
        )

    def embed_documents(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        return self._embed(texts, "document")

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._embed((text,), "query")[0]

    def _embed(
        self,
        texts: tuple[str, ...],
        input_type: str,
    ) -> tuple[tuple[float, ...], ...]:
        request = EmbeddingRequest(
            request_id=self._request_id("embed"),
            model_id=QWEN3_EMBEDDING_MODEL_ID,
            revision=QWEN3_EMBEDDING_REVISION,
            input_type=input_type,
            texts=texts,
            output_dimension=self._output_dimension,
        )
        response = self._transport.exchange(
            request,
            response_type=EmbeddingResponse,
        )
        _require_provenance(
            response.provenance,
            model_id=QWEN3_EMBEDDING_MODEL_ID,
            revision=QWEN3_EMBEDDING_REVISION,
        )
        if response.output_dimension != self._output_dimension:
            raise ValueError("Qwen3 embedding response dimension mismatch")
        if len(response.vectors) != len(texts):
            raise ValueError("Qwen3 embedding response count mismatch")
        return response.vectors

    def _request_id(self, operation: str) -> str:
        if self._request_id_factory is not None:
            return self._request_id_factory(operation)
        return f"{operation}-{uuid.uuid4().hex}"


class Qwen3RerankerProvider:
    def __init__(
        self,
        *,
        transport: ModelTransport,
        request_id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self._transport = transport
        self._request_id_factory = request_id_factory

    @property
    def provenance_identity(self) -> tuple[str, str]:
        return QWEN3_RERANKER_MODEL_ID, QWEN3_RERANKER_REVISION

    def rerank(
        self,
        *,
        query: str,
        evidence: tuple[HybridEvidence, ...],
    ) -> tuple[RerankedEvidence, ...]:
        if not evidence:
            return ()
        request = RerankRequest(
            request_id=self._request_id("rerank"),
            model_id=QWEN3_RERANKER_MODEL_ID,
            revision=QWEN3_RERANKER_REVISION,
            query=query,
            documents=tuple(
                RerankDocument(
                    document_id=item.evidence_id,
                    text=item.excerpt,
                )
                for item in evidence
            ),
        )
        response = self._transport.exchange(
            request,
            response_type=RerankResponse,
        )
        _require_provenance(
            response.provenance,
            model_id=QWEN3_RERANKER_MODEL_ID,
            revision=QWEN3_RERANKER_REVISION,
        )
        evidence_by_id = {item.evidence_id: item for item in evidence}
        response_ids = {item.document_id for item in response.scores}
        if response_ids != set(evidence_by_id):
            raise ValueError("Qwen3 reranker response candidate set mismatch")
        ranked_scores = sorted(
            response.scores,
            key=lambda item: (-item.score, item.document_id),
        )
        return tuple(
            RerankedEvidence(
                evidence=evidence_by_id[item.document_id],
                reranker_score=item.score,
                reranker_rank=rank,
                model_id=QWEN3_RERANKER_MODEL_ID,
                model_revision=QWEN3_RERANKER_REVISION,
            )
            for rank, item in enumerate(ranked_scores, start=1)
        )

    def _request_id(self, operation: str) -> str:
        if self._request_id_factory is not None:
            return self._request_id_factory(operation)
        return f"{operation}-{uuid.uuid4().hex}"


def _require_provenance(
    provenance: ModelProvenance,
    *,
    model_id: str,
    revision: str,
) -> None:
    if provenance.model_id != model_id or provenance.revision != revision:
        raise ValueError("Qwen3 model provenance mismatch")

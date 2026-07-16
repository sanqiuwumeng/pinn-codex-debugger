"""Metadata-scoped reciprocal-rank fusion with explicit conflict blocking."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from pinn_strategy_system.contracts import (
    EvidenceItem,
    RetrievalRequest,
    SourceRef,
)
from pinn_strategy_system.execution.retrieval import RetrievalProvider
from .vector_index import (
    EmbeddingProvider,
    LocalQdrantIndex,
)
from .qwen3 import RerankingProvider

from .models import (
    EvidenceClaim,
    EvidenceConflict,
    HybridEvidence,
    HybridRetrievalResponse,
    RetrievalScope,
    VectorHit,
)

RRF_OFFSET = 60
ORDINARY_CANDIDATE_POOL = 6
ALL_EVIDENCE_CANDIDATE_POOL = 10


@dataclass
class _Candidate:
    evidence_id: str
    source_ref: SourceRef
    artifact_range: str | None
    excerpt: str
    metadata: dict[str, Any]
    claims: tuple[EvidenceClaim, ...]
    deterministic_rank: int | None
    vector_rank: int | None
    provenance_validated: bool


class HybridRetriever:
    def __init__(
        self,
        *,
        deterministic_provider: RetrievalProvider,
        vector_index: LocalQdrantIndex,
        embedder: EmbeddingProvider,
        reranker: RerankingProvider,
    ) -> None:
        self._deterministic = deterministic_provider
        self._vector_index = vector_index
        self._embedder = embedder
        self._reranker = reranker

    def search(
        self,
        request: RetrievalRequest,
        *,
        scope: RetrievalScope,
    ) -> HybridRetrievalResponse:
        if request.project_id != scope.project_id:
            raise ValueError("retrieval request and metadata scope project mismatch")
        candidate_limit = max(
            request.max_sections,
            (
                ALL_EVIDENCE_CANDIDATE_POOL
                if scope.evidence_mode == "all"
                else ORDINARY_CANDIDATE_POOL
            ),
        )
        candidate_request = request.model_copy(
            update={"max_sections": candidate_limit}
        )
        deterministic = self._deterministic.search(candidate_request)
        vector_hits = self._vector_index.search(
            query_vector=self._embedder.embed_query(request.query),
            scope=scope,
            limit=candidate_limit,
        )
        candidates = tuple(
            sorted(
                _fused_candidates(
                    deterministic.evidence,
                    vector_hits,
                ),
                key=lambda item: (-_rrf_score(item), item.evidence_id),
            )[:candidate_limit]
        )
        conflicts = _conflicts(candidates)
        conflict_keys = {
            conflict.claim_key
            for conflict in conflicts
        }
        fused_evidence = tuple(
            _to_evidence(candidate, conflict_keys)
            for candidate in candidates
        )
        reranked = self._reranker.rerank(
            query=request.query,
            evidence=fused_evidence,
        )
        ranked_evidence = tuple(
            item.evidence.model_copy(
                update={
                    "reranker_score": item.reranker_score,
                    "reranker_rank": item.reranker_rank,
                    "reranker_model_id": item.model_id,
                    "reranker_model_revision": item.model_revision,
                }
            )
            for item in reranked
        )
        evidence = tuple(
            sorted(
                ranked_evidence,
                key=lambda item: (
                    not bool(item.conflict_keys),
                    item.reranker_rank,
                    item.evidence_id,
                ),
            )[: request.max_sections]
        )
        model_label = (
            f"{reranked[0].model_id}@{reranked[0].model_revision}"
            if reranked
            else "no-rerank-candidates"
        )
        return HybridRetrievalResponse(
            request_id=request.request_id,
            backend=(
                f"{deterministic.backend}+qdrant-local+rrf+{model_label}"
            ),
            evidence=evidence,
            conflicts=conflicts,
            decision_safe=(
                bool(evidence)
                and not conflicts
                and all(item.provenance_validated for item in evidence)
            ),
            read_only=True,
        )


def _fused_candidates(
    deterministic: tuple[EvidenceItem, ...],
    vector_hits: tuple[VectorHit, ...],
) -> tuple[_Candidate, ...]:
    candidates: dict[str, _Candidate] = {}
    for rank, item in enumerate(deterministic, start=1):
        key = _range_key(
            item.source_uri,
            item.line_start,
            item.line_end,
            None,
        )
        claims = _claims_from_metadata(item.metadata)
        candidates[key] = _Candidate(
            evidence_id=_stable_evidence_id(key),
            source_ref=SourceRef(
                uri=item.source_uri,
                sha256=item.source_sha256,
                line_start=item.line_start,
                line_end=item.line_end,
            ),
            artifact_range=None,
            excerpt=item.excerpt,
            metadata=dict(item.metadata),
            claims=claims,
            deterministic_rank=rank,
            vector_rank=None,
            provenance_validated=True,
        )

    for rank, hit in enumerate(vector_hits, start=1):
        document = hit.document
        chunk = document.chunk
        source = chunk.metadata.source_ref
        key = _range_key(
            source.uri,
            source.line_start,
            source.line_end,
            chunk.metadata.artifact_range,
        )
        existing = candidates.get(key)
        if existing is None:
            candidates[key] = _Candidate(
                evidence_id=chunk.chunk_id,
                source_ref=source,
                artifact_range=chunk.metadata.artifact_range,
                excerpt=chunk.text,
                metadata=chunk.metadata.model_dump(mode="json"),
                claims=document.claims,
                deterministic_rank=None,
                vector_rank=rank,
                provenance_validated=True,
            )
            continue
        existing.evidence_id = chunk.chunk_id
        existing.vector_rank = rank
        existing.claims = tuple(
            dict.fromkeys((*existing.claims, *document.claims))
        )
        existing.metadata = {
            **chunk.metadata.model_dump(mode="json"),
            **existing.metadata,
        }
    return tuple(candidates.values())


def _claims_from_metadata(metadata: dict[str, Any]) -> tuple[EvidenceClaim, ...]:
    raw = metadata.get("claims", ())
    if not isinstance(raw, (list, tuple)):
        return ()
    claims: list[EvidenceClaim] = []
    for item in raw:
        if isinstance(item, dict):
            claims.append(EvidenceClaim.model_validate(item))
    return tuple(claims)


def _conflicts(
    candidates: tuple[_Candidate, ...],
) -> tuple[EvidenceConflict, ...]:
    grouped: dict[str, dict[str, set[str]]] = {}
    for candidate in candidates:
        for claim in candidate.claims:
            values = grouped.setdefault(claim.key, {})
            values.setdefault(claim.value, set()).add(candidate.evidence_id)
    conflicts: list[EvidenceConflict] = []
    for claim_key, values in sorted(grouped.items()):
        if len(values) < 2:
            continue
        evidence_ids = tuple(
            sorted(
                {
                    evidence_id
                    for ids in values.values()
                    for evidence_id in ids
                }
            )
        )
        conflicts.append(
            EvidenceConflict(
                claim_key=claim_key,
                claim_values=tuple(sorted(values)),
                evidence_ids=evidence_ids,
            )
        )
    return tuple(conflicts)


def _to_evidence(
    candidate: _Candidate,
    conflict_keys: set[str],
) -> HybridEvidence:
    candidate_claim_keys = {claim.key for claim in candidate.claims}
    return HybridEvidence(
        evidence_id=candidate.evidence_id,
        source_ref=candidate.source_ref,
        artifact_range=candidate.artifact_range,
        excerpt=candidate.excerpt,
        metadata=candidate.metadata,
        deterministic_rank=candidate.deterministic_rank,
        vector_rank=candidate.vector_rank,
        fused_score=_rrf_score(candidate),
        claims=candidate.claims,
        conflict_keys=tuple(sorted(candidate_claim_keys & conflict_keys)),
        provenance_validated=candidate.provenance_validated,
    )


def _rrf_score(candidate: _Candidate) -> float:
    ranks = (
        candidate.deterministic_rank,
        candidate.vector_rank,
    )
    return sum(
        1.0 / (RRF_OFFSET + rank)
        for rank in ranks
        if rank is not None
    )


def _range_key(
    uri: str,
    line_start: int | None,
    line_end: int | None,
    artifact_range: str | None,
) -> str:
    return f"{uri}|{line_start}|{line_end}|{artifact_range}"


def _stable_evidence_id(key: str) -> str:
    return f"det-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]}"

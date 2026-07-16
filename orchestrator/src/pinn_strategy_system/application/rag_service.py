"""Application-level RAG rebuild and query services."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pinn_strategy_system.retrieval import (
    EvidenceConflict,
    FilesystemKnowledgeSource,
    HybridEvidence,
    QdrantIndexGovernance,
    Qwen3EmbeddingProvider,
    Qwen3RerankerProvider,
    RetrievalScope,
)

from .contracts import ApplicationResult, OperationOutcome, OperatorCase


class ModelTransportFactory(Protocol):
    def __call__(self, role: str): ...


class RagApplicationService:
    def __init__(
        self,
        *,
        runtime_root: Path,
        transport_factory: ModelTransportFactory,
    ) -> None:
        if not runtime_root.is_absolute():
            raise ValueError("RAG runtime root must be absolute")
        rag_root = runtime_root.resolve(strict=False) / "rag"
        vector_root = rag_root / "qdrant"
        state_root = rag_root / "index-state"
        vector_root.mkdir(parents=True, exist_ok=True)
        state_root.mkdir(parents=True, exist_ok=True)
        self._governance = QdrantIndexGovernance(
            qdrant_root=vector_root,
            state_root=state_root,
        )
        self._transport_factory = transport_factory

    def rebuild(self, *, source_root: Path, case: OperatorCase) -> ApplicationResult:
        if case.chunking_policy is None or case.retrieval_scope is None:
            return ApplicationResult(
                command="rag rebuild",
                outcome=OperationOutcome.NEEDS_INPUT,
                code="NEEDS_RAG_POLICY",
                message="RAG rebuild requires chunking and retrieval scope contracts.",
                workflow_id=case.request.workflow_id,
                data={},
            )
        source = FilesystemKnowledgeSource(source_root)
        with self._transport_factory("embedding") as transport:
            embedder = Qwen3EmbeddingProvider(transport=transport)
            build = self._governance.build_candidate(
                source=source,
                embedder=embedder,
                chunking_policy=case.chunking_policy,
            )
            canary = self._governance.canary(
                build=build,
                query=case.request.objective,
                scope=case.retrieval_scope,
                embedder=embedder,
            )
        if not canary.passed:
            return ApplicationResult(
                command="rag rebuild",
                outcome=OperationOutcome.GATE_REJECTED,
                code="INDEX_CANARY_FAILED",
                message="Candidate index failed its query canary.",
                workflow_id=case.request.workflow_id,
                data={
                    "build": build.model_dump(mode="json"),
                    "canary": canary.model_dump(mode="json"),
                },
            )
        activation = self._governance.activate(build=build, canary=canary)
        return ApplicationResult(
            command="rag rebuild",
            outcome=OperationOutcome.SUCCESS,
            code="INDEX_ACTIVATED",
            message="Content-addressed index passed canary and was activated.",
            workflow_id=case.request.workflow_id,
            data={
                "build": build.model_dump(mode="json"),
                "canary": canary.model_dump(mode="json"),
                "active_index": activation.model_dump(mode="json"),
            },
        )

    def query(
        self,
        *,
        case: OperatorCase,
        query: str,
    ) -> ApplicationResult:
        scope = case.retrieval_scope
        if scope is None:
            return ApplicationResult(
                command="rag query",
                outcome=OperationOutcome.NEEDS_INPUT,
                code="NEEDS_RETRIEVAL_SCOPE",
                message="RAG query requires an explicit retrieval scope.",
                workflow_id=case.request.workflow_id,
                data={},
            )
        limit = max(10 if scope.evidence_mode == "all" else 6, 1)
        active = self._governance.active()
        if active is None:
            return ApplicationResult(
                command="rag query",
                outcome=OperationOutcome.NEEDS_INPUT,
                code="NEEDS_ACTIVE_INDEX",
                message="RAG query requires an active governed index.",
                workflow_id=case.request.workflow_id,
                data={},
            )
        with self._transport_factory("embedding") as transport:
            embedder = Qwen3EmbeddingProvider(transport=transport)
            query_vector = embedder.embed_query(query)
        with self._governance.open_active() as index:
            hits = index.search(
                query_vector=query_vector,
                scope=scope,
                limit=limit,
            )
        if len(hits) < limit:
            return ApplicationResult(
                command="rag query",
                outcome=OperationOutcome.GATE_REJECTED,
                code="INSUFFICIENT_CANDIDATES",
                message="Active index cannot satisfy the governed candidate pool.",
                workflow_id=case.request.workflow_id,
                data={
                    "active_index": active.model_dump(mode="json"),
                    "required_candidates": limit,
                    "observed_candidates": len(hits),
                },
            )
        evidence = tuple(
            HybridEvidence(
                evidence_id=hit.document.chunk.chunk_id,
                source_ref=hit.document.chunk.metadata.source_ref,
                artifact_range=hit.document.chunk.metadata.artifact_range,
                excerpt=hit.document.chunk.text,
                metadata=hit.document.chunk.metadata.model_dump(mode="json"),
                vector_rank=rank,
                fused_score=1.0 / (60 + rank),
                claims=hit.document.claims,
                provenance_validated=True,
            )
            for rank, hit in enumerate(hits, start=1)
        )
        conflicts = _evidence_conflicts(evidence)
        conflict_keys = {item.claim_key for item in conflicts}
        evidence = tuple(
            item.model_copy(
                update={
                    "conflict_keys": tuple(
                        sorted({claim.key for claim in item.claims} & conflict_keys)
                    )
                }
            )
            for item in evidence
        )
        with self._transport_factory("reranker") as transport:
            ranked = Qwen3RerankerProvider(transport=transport).rerank(
                query=query,
                evidence=evidence,
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
            for item in ranked
        )
        return ApplicationResult(
            command="rag query",
            outcome=OperationOutcome.SUCCESS,
            code=("CONFLICTS_VISIBLE" if conflicts else "EVIDENCE_READY"),
            message="Active-index evidence was retrieved and reranked.",
            workflow_id=case.request.workflow_id,
            data={
                "active_index": active.model_dump(mode="json"),
                "candidate_count": len(evidence),
                "evidence": [item.model_dump(mode="json") for item in ranked_evidence],
                "conflicts": [item.model_dump(mode="json") for item in conflicts],
                "decision_safe": bool(ranked_evidence) and not conflicts,
            },
        )


def _evidence_conflicts(
    evidence: tuple[HybridEvidence, ...],
) -> tuple[EvidenceConflict, ...]:
    grouped: dict[str, dict[str, set[str]]] = {}
    for item in evidence:
        for claim in item.claims:
            grouped.setdefault(claim.key, {}).setdefault(claim.value, set()).add(
                item.evidence_id
            )
    conflicts = []
    for key, values in sorted(grouped.items()):
        if len(values) < 2:
            continue
        conflicts.append(
            EvidenceConflict(
                claim_key=key,
                claim_values=tuple(sorted(values)),
                evidence_ids=tuple(
                    sorted(
                        evidence_id
                        for identifiers in values.values()
                        for evidence_id in identifiers
                    )
                ),
            )
        )
    return tuple(conflicts)

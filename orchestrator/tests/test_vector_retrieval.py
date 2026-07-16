from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.contracts import (  # noqa: E402
    ChunkMetadata,
    EvidenceItem,
    KnowledgeChunk,
    RetrievalRequest,
    RetrievalResponse,
    SourceRef,
)
from pinn_strategy_system.retrieval import (  # noqa: E402
    EvidenceClaim,
    FilesystemKnowledgeSource,
    HybridRetriever,
    IndexedKnowledgeDocument,
    LocalQdrantIndex,
    ProvenanceError,
    RerankedEvidence,
    RetrievalScope,
)


class DeterministicEmbedding:
    def embed_documents(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        return tuple(self.embed_query(text) for text in texts)

    def embed_query(self, text: str) -> tuple[float, ...]:
        lowered = text.lower()
        return (
            float(lowered.count("boundary") + lowered.count("边界")),
            float(lowered.count("temperature") + lowered.count("温度")),
            float(lowered.count("optimizer") + lowered.count("优化器")),
        )


class FixedDeterministicProvider:
    def __init__(self, evidence: tuple[EvidenceItem, ...], source_sha: str) -> None:
        self._evidence = evidence
        self._source_sha = source_sha

    def search(self, request: RetrievalRequest) -> RetrievalResponse:
        return RetrievalResponse(
            request_id=request.request_id,
            provider="fixed-deterministic",
            backend="frozen-rules",
            source_sha256=self._source_sha,
            evidence=self._evidence,
            read_only=True,
        )


class DeterministicReranker:
    def __init__(self) -> None:
        self.candidate_counts: list[int] = []

    def rerank(self, *, query, evidence):
        self.candidate_counts.append(len(evidence))
        ranked = sorted(
            evidence,
            key=lambda item: (-item.fused_score, item.evidence_id),
        )
        return tuple(
            RerankedEvidence(
                evidence=item,
                reranker_score=item.fused_score,
                reranker_rank=rank,
                model_id="test/deterministic-reranker",
                model_revision="0" * 40,
            )
            for rank, item in enumerate(ranked, start=1)
        )


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_source(
    root: Path,
    specs: tuple[dict, ...],
) -> tuple[FilesystemKnowledgeSource, tuple[IndexedKnowledgeDocument, ...], str]:
    text = "\n".join(str(spec["text"]) for spec in specs)
    source_file = root / "handbook.md"
    source_file.write_text(text, encoding="utf-8")
    source_sha = hashlib.sha256(source_file.read_bytes()).hexdigest()
    documents: list[IndexedKnowledgeDocument] = []
    for line, spec in enumerate(specs, start=1):
        chunk_text = str(spec["text"])
        document = IndexedKnowledgeDocument(
            chunk=KnowledgeChunk(
                chunk_id=str(spec["chunk_id"]),
                text=chunk_text,
                chunk_sha256=_sha(chunk_text),
                metadata=ChunkMetadata(
                    project_id=str(spec["project_id"]),
                    source_ref=SourceRef(
                        uri=source_file.as_uri(),
                        sha256=source_sha,
                        line_start=line,
                        line_end=line,
                    ),
                    repo_commit="abc123",
                    model_family="PINN",
                    pde_family=str(spec.get("pde_family", "cross-domain")),
                    task_type=str(spec.get("task_type", "diagnosis")),
                    domain_provider_id=spec.get("domain_provider_id"),
                    output_channels=tuple(spec.get("output_channels", ())),
                    dimensional_signatures=tuple(
                        spec.get("dimensional_signatures", ())
                    ),
                    failure_signatures=tuple(spec.get("failure_signatures", ())),
                    framework="PyTorch",
                    document_type="HANDBOOK",
                    validation_status="SOURCE_VERIFIED",
                    valid_from=datetime(2026, 7, 16, tzinfo=UTC),
                    language=str(spec.get("language", "en")),
                ),
            ),
            applicable_versions=tuple(spec.get("versions", ("v1",))),
            claims=tuple(spec.get("claims", ())),
        )
        documents.append(document)
        (root / f"{document.chunk.chunk_id}.index.json").write_text(
            document.model_dump_json(indent=2),
            encoding="utf-8",
        )
    return FilesystemKnowledgeSource(root), tuple(documents), source_sha


class VectorRetrievalTests(unittest.TestCase):
    def test_metadata_scope_filters_before_vector_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "knowledge"
            vectors = root / "vectors"
            knowledge.mkdir()
            vectors.mkdir()
            source, _, _ = _write_source(
                knowledge,
                (
                    {
                        "chunk_id": "p1-boundary",
                        "project_id": "project-1",
                        "text": "boundary residual diagnosis",
                        "pde_family": "burgers",
                        "task_type": "forward",
                        "domain_provider_id": "pinn.residual.v1",
                        "output_channels": ("u",),
                        "dimensional_signatures": ("dimensionless",),
                        "failure_signatures": ("boundary_residual",),
                    },
                    {
                        "chunk_id": "p2-boundary",
                        "project_id": "project-2",
                        "text": "boundary residual diagnosis",
                        "pde_family": "burgers",
                    },
                    {
                        "chunk_id": "p1-optimizer",
                        "project_id": "project-1",
                        "text": "optimizer schedule",
                        "pde_family": "heat-equation",
                    },
                    {
                        "chunk_id": "p1-heat-boundary",
                        "project_id": "project-1",
                        "text": "boundary residual diagnosis",
                        "pde_family": "heat-equation",
                        "task_type": "forward",
                        "domain_provider_id": "heat-transfer.phase-change.v1",
                        "output_channels": ("temperature",),
                        "dimensional_signatures": ("temperature",),
                        "failure_signatures": ("boundary_residual",),
                    },
                ),
            )
            with LocalQdrantIndex(
                root=vectors,
                collection_name="knowledge",
                vector_size=3,
            ) as index:
                self.assertEqual(
                    index.rebuild(
                        source=source,
                        embedder=DeterministicEmbedding(),
                    ),
                    4,
                )
                hits = index.search(
                    query_vector=DeterministicEmbedding().embed_query(
                        "boundary"
                    ),
                    scope=RetrievalScope(
                        project_id="project-1",
                        document_types=("HANDBOOK",),
                        model_family="PINN",
                        pde_family="burgers",
                        task_type="forward",
                        domain_provider_id="pinn.residual.v1",
                        output_channels=("u",),
                        dimensional_signatures=("dimensionless",),
                        failure_signatures=("boundary_residual",),
                        framework="PyTorch",
                        applicable_version="v1",
                    ),
                    limit=5,
                )
                self.assertTrue(hits)
                self.assertTrue(
                    all(
                        hit.document.chunk.metadata.project_id == "project-1"
                        for hit in hits
                    )
                )
                self.assertNotIn(
                    "p2-boundary",
                    tuple(hit.document.chunk.chunk_id for hit in hits),
                )
                self.assertNotIn(
                    "p1-heat-boundary",
                    tuple(hit.document.chunk.chunk_id for hit in hits),
                )

    def test_index_deletion_and_rebuild_preserve_authoritative_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "knowledge"
            vectors = root / "vectors"
            artifacts = root / "artifacts"
            knowledge.mkdir()
            vectors.mkdir()
            artifacts.mkdir()
            artifact_file = artifacts / "metrics.json"
            artifact_file.write_text('{"rmse": 1.0}', encoding="utf-8")
            source, _, _ = _write_source(
                knowledge,
                (
                    {
                        "chunk_id": "boundary",
                        "project_id": "project-1",
                        "text": "boundary evidence",
                    },
                ),
            )
            catalog_file = knowledge / "boundary.index.json"
            handbook_file = knowledge / "handbook.md"
            with LocalQdrantIndex(
                root=vectors,
                collection_name="knowledge",
                vector_size=3,
            ) as index:
                index.rebuild(
                    source=source,
                    embedder=DeterministicEmbedding(),
                )
                self.assertEqual(index.count(), 1)
                self.assertTrue(index.delete_collection())
                self.assertEqual(index.count(), 0)
                self.assertTrue(catalog_file.exists())
                self.assertTrue(handbook_file.exists())
                self.assertTrue(artifact_file.exists())
                self.assertEqual(
                    index.rebuild(
                        source=source,
                        embedder=DeterministicEmbedding(),
                    ),
                    1,
                )
                self.assertEqual(index.count(), 1)

    def test_hybrid_fusion_flags_conflicting_claims_and_blocks_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "knowledge"
            vectors = root / "vectors"
            knowledge.mkdir()
            vectors.mkdir()
            source, documents, source_sha = _write_source(
                knowledge,
                (
                    {
                        "chunk_id": "kelvin",
                        "project_id": "project-1",
                        "text": "temperature unit boundary evidence",
                        "claims": (
                            EvidenceClaim(
                                key="temperature_unit",
                                value="K",
                            ),
                        ),
                    },
                    {
                        "chunk_id": "celsius",
                        "project_id": "project-1",
                        "text": "temperature unit boundary contradiction",
                        "claims": (
                            EvidenceClaim(
                                key="temperature_unit",
                                value="degC",
                            ),
                        ),
                    },
                ),
            )
            first = documents[0].chunk
            deterministic = FixedDeterministicProvider(
                (
                    EvidenceItem(
                        source_uri=first.metadata.source_ref.uri,
                        source_sha256=source_sha,
                        heading="Temperature units",
                        line_start=first.metadata.source_ref.line_start,
                        line_end=first.metadata.source_ref.line_end,
                        excerpt=first.text,
                        score=1.0,
                    ),
                ),
                source_sha,
            )
            with LocalQdrantIndex(
                root=vectors,
                collection_name="knowledge",
                vector_size=3,
            ) as index:
                index.rebuild(
                    source=source,
                    embedder=DeterministicEmbedding(),
                )
                retriever = HybridRetriever(
                    deterministic_provider=deterministic,
                    vector_index=index,
                    embedder=DeterministicEmbedding(),
                    reranker=DeterministicReranker(),
                )
                response = retriever.search(
                    RetrievalRequest(
                        request_id="request-1",
                        project_id="project-1",
                        query="temperature unit boundary",
                        max_sections=5,
                    ),
                    scope=RetrievalScope(project_id="project-1"),
                )
                self.assertFalse(response.decision_safe)
                self.assertEqual(
                    tuple(item.claim_key for item in response.conflicts),
                    ("temperature_unit",),
                )
                fused = next(
                    item for item in response.evidence
                    if item.evidence_id == "kelvin"
                )
                self.assertIsNotNone(fused.deterministic_rank)
                self.assertIsNotNone(fused.vector_rank)
                self.assertEqual(fused.conflict_keys, ("temperature_unit",))

    def test_rebuild_rejects_tampered_chunk_before_replacing_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "knowledge"
            vectors = root / "vectors"
            knowledge.mkdir()
            vectors.mkdir()
            source, documents, _ = _write_source(
                knowledge,
                (
                    {
                        "chunk_id": "boundary",
                        "project_id": "project-1",
                        "text": "boundary evidence",
                    },
                ),
            )
            tampered = documents[0].model_copy(
                update={
                    "chunk": documents[0].chunk.model_copy(
                        update={"chunk_sha256": "0" * 64}
                    )
                }
            )
            (knowledge / "boundary.index.json").write_text(
                tampered.model_dump_json(indent=2),
                encoding="utf-8",
            )
            with LocalQdrantIndex(
                root=vectors,
                collection_name="knowledge",
                vector_size=3,
            ) as index:
                with self.assertRaises(ProvenanceError):
                    index.rebuild(
                        source=source,
                        embedder=DeterministicEmbedding(),
                    )
                self.assertEqual(index.count(), 0)

    def test_search_revalidates_authoritative_source_after_indexing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "knowledge"
            vectors = root / "vectors"
            knowledge.mkdir()
            vectors.mkdir()
            source, _, _ = _write_source(
                knowledge,
                (
                    {
                        "chunk_id": "boundary",
                        "project_id": "project-1",
                        "text": "boundary evidence",
                    },
                ),
            )
            with LocalQdrantIndex(
                root=vectors,
                collection_name="knowledge",
                vector_size=3,
            ) as index:
                index.rebuild(
                    source=source,
                    embedder=DeterministicEmbedding(),
                )
                (knowledge / "handbook.md").write_text(
                    "source changed after indexing",
                    encoding="utf-8",
                )
                with self.assertRaises(ProvenanceError):
                    index.search(
                        query_vector=DeterministicEmbedding().embed_query(
                            "boundary"
                        ),
                        scope=RetrievalScope(project_id="project-1"),
                        limit=3,
                    )

    def test_empty_retrieval_is_not_decision_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            vectors = Path(temp) / "vectors"
            vectors.mkdir()
            empty_sha = "0" * 64
            deterministic = FixedDeterministicProvider((), empty_sha)
            with LocalQdrantIndex(
                root=vectors,
                collection_name="knowledge",
                vector_size=3,
            ) as index:
                retriever = HybridRetriever(
                    deterministic_provider=deterministic,
                    vector_index=index,
                    embedder=DeterministicEmbedding(),
                    reranker=DeterministicReranker(),
                )
                response = retriever.search(
                    RetrievalRequest(
                        request_id="request-empty",
                        project_id="project-1",
                        query="unknown",
                    ),
                    scope=RetrievalScope(project_id="project-1"),
                )
                self.assertFalse(response.decision_safe)
                self.assertEqual(response.evidence, ())

    def test_deterministic_evidence_remains_when_vector_index_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            vectors = Path(temp) / "vectors"
            vectors.mkdir()
            source_sha = "1" * 64
            deterministic = FixedDeterministicProvider(
                (
                    EvidenceItem(
                        source_uri="artifact://handbook/frozen",
                        source_sha256=source_sha,
                        heading="Frozen deterministic evidence",
                        line_start=1,
                        line_end=3,
                        excerpt="Boundary evidence remains available.",
                        score=1.0,
                    ),
                ),
                source_sha,
            )
            with LocalQdrantIndex(
                root=vectors,
                collection_name="knowledge",
                vector_size=3,
            ) as index:
                retriever = HybridRetriever(
                    deterministic_provider=deterministic,
                    vector_index=index,
                    embedder=DeterministicEmbedding(),
                    reranker=DeterministicReranker(),
                )
                response = retriever.search(
                    RetrievalRequest(
                        request_id="request-deterministic-only",
                        project_id="project-1",
                        query="boundary",
                    ),
                    scope=RetrievalScope(project_id="project-1"),
                )
                self.assertTrue(response.decision_safe)
                self.assertEqual(len(response.evidence), 1)
                self.assertEqual(response.evidence[0].deterministic_rank, 1)
                self.assertIsNone(response.evidence[0].vector_rank)

    def test_candidate_pool_is_six_for_single_and_ten_for_all_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "knowledge"
            vectors = root / "vectors"
            knowledge.mkdir()
            vectors.mkdir()
            specs = tuple(
                {
                    "chunk_id": f"boundary-{index:02d}",
                    "project_id": "project-1",
                    "text": f"boundary evidence {index:02d}",
                }
                for index in range(12)
            )
            source, _, source_sha = _write_source(knowledge, specs)
            deterministic = FixedDeterministicProvider((), source_sha)
            reranker = DeterministicReranker()
            with LocalQdrantIndex(
                root=vectors,
                collection_name="knowledge",
                vector_size=3,
            ) as index:
                index.rebuild(
                    source=source,
                    embedder=DeterministicEmbedding(),
                )
                retriever = HybridRetriever(
                    deterministic_provider=deterministic,
                    vector_index=index,
                    embedder=DeterministicEmbedding(),
                    reranker=reranker,
                )
                for request_id, mode in (
                    ("request-single", "single"),
                    ("request-all", "all"),
                ):
                    retriever.search(
                        RetrievalRequest(
                            request_id=request_id,
                            project_id="project-1",
                            query="boundary",
                            max_sections=5,
                        ),
                        scope=RetrievalScope(
                            project_id="project-1",
                            evidence_mode=mode,
                        ),
                    )
            self.assertEqual(reranker.candidate_counts, [6, 10])


if __name__ == "__main__":
    unittest.main()

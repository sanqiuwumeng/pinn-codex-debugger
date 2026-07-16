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
    ChunkingPolicy,
    ChunkMetadata,
    KnowledgeChunk,
    SourceRef,
)
from pinn_strategy_system.retrieval import (  # noqa: E402
    FilesystemKnowledgeSource,
    IndexedKnowledgeDocument,
    QdrantIndexGovernance,
    RetrievalScope,
)


class GovernedEmbedding:
    def __init__(self, revision: str = "1" * 40) -> None:
        self.revision = revision

    @property
    def provenance_identity(self):
        return "test/embedding", self.revision, 3

    def embed_documents(self, texts):
        return tuple(self.embed_query(text) for text in texts)

    def embed_query(self, text):
        lowered = text.casefold()
        return (
            float("boundary" in lowered),
            float("residual" in lowered),
            1.0,
        )


def _source(root: Path, *, chunk_id: str, text: str) -> FilesystemKnowledgeSource:
    root.mkdir()
    handbook = root / "handbook.md"
    handbook.write_text(text, encoding="utf-8")
    source_sha = hashlib.sha256(handbook.read_bytes()).hexdigest()
    document = IndexedKnowledgeDocument(
        chunk=KnowledgeChunk(
            chunk_id=chunk_id,
            text=text,
            chunk_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            metadata=ChunkMetadata(
                project_id="project-1",
                source_ref=SourceRef(
                    uri=handbook.as_uri(),
                    sha256=source_sha,
                    line_start=1,
                    line_end=1,
                ),
                repo_commit="abc123",
                model_family="PINN",
                document_type="HANDBOOK",
                validation_status="SOURCE_VERIFIED",
                valid_from=datetime(2026, 7, 16, tzinfo=UTC),
                language="en",
            ),
        ),
    )
    (root / f"{chunk_id}.index.json").write_text(
        document.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return FilesystemKnowledgeSource(root)


def _policy(max_characters: int = 2048) -> ChunkingPolicy:
    return ChunkingPolicy(
        policy_id="governed-v1",
        max_characters=max_characters,
        overlap_characters=128,
        document_types=("HANDBOOK",),
    )


class IndexGovernanceTests(unittest.TestCase):
    def test_build_canary_activate_and_rollback_keep_both_collections(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            qdrant = root / "qdrant"
            state = root / "state"
            qdrant.mkdir()
            state.mkdir()
            first_source = _source(
                root / "knowledge-1",
                chunk_id="boundary-v1",
                text="boundary residual evidence",
            )
            second_source = _source(
                root / "knowledge-2",
                chunk_id="boundary-v2",
                text="boundary residual updated evidence",
            )
            embedder = GovernedEmbedding()
            governance = QdrantIndexGovernance(
                qdrant_root=qdrant,
                state_root=state,
            )
            first = governance.build_candidate(
                source=first_source,
                embedder=embedder,
                chunking_policy=_policy(),
            )
            first_canary = governance.canary(
                build=first,
                query="boundary residual",
                scope=RetrievalScope(project_id="project-1"),
                embedder=embedder,
                required_hit_ids=("boundary-v1",),
            )
            first_active = governance.activate(
                build=first,
                canary=first_canary,
            )
            second = governance.build_candidate(
                source=second_source,
                embedder=embedder,
                chunking_policy=_policy(),
            )
            second_canary = governance.canary(
                build=second,
                query="boundary residual updated",
                scope=RetrievalScope(project_id="project-1"),
                embedder=embedder,
                required_hit_ids=("boundary-v2",),
            )
            second_active = governance.activate(
                build=second,
                canary=second_canary,
            )
            self.assertNotEqual(
                first_active.active.collection_name,
                second_active.active.collection_name,
            )
            self.assertEqual(second_active.previous, first_active.active)
            rolled_back = governance.rollback()
            self.assertEqual(rolled_back.active, first_active.active)
            self.assertEqual(rolled_back.previous, second_active.active)
            self.assertEqual(
                rolled_back.canary.identity_sha256,
                first_active.active.identity_sha256,
            )
            with governance.open_active() as active_index:
                self.assertEqual(active_index.count(), 1)
            backups = tuple((state / "activation-backups").rglob("*backup*"))
            self.assertGreaterEqual(len(backups), 2)
            self.assertGreaterEqual(
                len(tuple((state / "activation-history").glob("*.json"))),
                3,
            )

    def test_failed_canary_cannot_activate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            qdrant = root / "qdrant"
            state = root / "state"
            qdrant.mkdir()
            state.mkdir()
            source = _source(
                root / "knowledge",
                chunk_id="boundary",
                text="boundary evidence",
            )
            embedder = GovernedEmbedding()
            governance = QdrantIndexGovernance(
                qdrant_root=qdrant,
                state_root=state,
            )
            build = governance.build_candidate(
                source=source,
                embedder=embedder,
                chunking_policy=_policy(),
            )
            canary = governance.canary(
                build=build,
                query="boundary",
                scope=RetrievalScope(project_id="project-1"),
                embedder=embedder,
                required_hit_ids=("missing",),
            )
            self.assertFalse(canary.passed)
            with self.assertRaisesRegex(ValueError, "cannot be activated"):
                governance.activate(build=build, canary=canary)
            self.assertIsNone(governance.active())

    def test_identity_changes_with_model_chunking_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            qdrant = root / "qdrant"
            state = root / "state"
            qdrant.mkdir()
            state.mkdir()
            source = _source(
                root / "knowledge",
                chunk_id="boundary",
                text="boundary evidence",
            )
            governance = QdrantIndexGovernance(
                qdrant_root=qdrant,
                state_root=state,
            )
            baseline = governance.identity(
                source=source,
                embedder=GovernedEmbedding(),
                chunking_policy=_policy(),
            )
            changed_model = governance.identity(
                source=source,
                embedder=GovernedEmbedding("2" * 40),
                chunking_policy=_policy(),
            )
            changed_policy = governance.identity(
                source=source,
                embedder=GovernedEmbedding(),
                chunking_policy=_policy(4096),
            )
            self.assertEqual(
                len(
                    {
                        baseline.identity_sha256,
                        changed_model.identity_sha256,
                        changed_policy.identity_sha256,
                    }
                ),
                3,
            )


if __name__ == "__main__":
    unittest.main()

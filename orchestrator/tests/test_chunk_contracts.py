from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.contracts import (  # noqa: E402
    ChunkMetadata,
    ChunkingPolicy,
    KnowledgeChunk,
    SourceRef,
)

SHA = "4" * 64


class ChunkContractTests(unittest.TestCase):
    def test_chunk_policy_preserves_structural_boundaries(self) -> None:
        policy = ChunkingPolicy(
            policy_id="handbook-v1",
            max_characters=2000,
            overlap_characters=200,
            document_types=("HANDBOOK", "CODE_MAP"),
        )
        self.assertTrue(policy.preserve_headings)
        self.assertTrue(policy.preserve_code_blocks)

    def test_line_based_chunk_has_complete_rebuildable_provenance(self) -> None:
        chunk = KnowledgeChunk(
            chunk_id="handbook-12-1",
            text="Localized residual evidence with a traceable source.",
            chunk_sha256=SHA,
            metadata=ChunkMetadata(
                project_id="project-1",
                source_ref=SourceRef(
                    uri="file:///repo/handbook.md",
                    sha256=SHA,
                    line_start=120,
                    line_end=140,
                ),
                repo_commit="abc123",
                model_family="PINN",
                pde_family="burgers",
                task_type="forward",
                domain_provider_id="pinn.residual.v1",
                output_channels=("u",),
                dimensional_signatures=("dimensionless",),
                failure_signatures=("localized_residual",),
                framework="PyTorch",
                document_type="HANDBOOK",
                validation_status="SOURCE_VERIFIED",
                valid_from=datetime(2026, 7, 15, tzinfo=UTC),
                language="zh-CN",
            ),
        )
        self.assertEqual(chunk.metadata.source_ref.line_start, 120)
        self.assertEqual(chunk.metadata.validation_status, "SOURCE_VERIFIED")
        self.assertEqual(chunk.metadata.pde_family, "burgers")

    def test_artifact_chunk_requires_range_when_no_lines_exist(self) -> None:
        with self.assertRaises(ValidationError):
            ChunkMetadata(
                project_id="project-1",
                source_ref=SourceRef(
                    uri="artifact://reports/run-1",
                    sha256=SHA,
                ),
                experiment_id="experiment-1",
                run_id="run-1",
                dataset_hash=SHA,
                environment_hash=SHA,
                document_type="EXPERIMENT_REPORT",
                validation_status="RESULT_VALIDATED",
                valid_from=datetime(2026, 7, 15, tzinfo=UTC),
                language="en",
            )

    def test_artifact_range_supports_validated_experiment_report(self) -> None:
        metadata = ChunkMetadata(
            project_id="project-1",
            source_ref=SourceRef(
                uri="artifact://reports/run-1",
                sha256=SHA,
            ),
            artifact_range="json-pointer:/prediction_analysis/findings/0",
            experiment_id="experiment-1",
            run_id="run-1",
            dataset_hash=SHA,
            environment_hash=SHA,
            model_family="PINN",
            framework="PyTorch",
            document_type="EXPERIMENT_REPORT",
            validation_status="RESULT_VALIDATED",
            valid_from=datetime(2026, 7, 15, tzinfo=UTC),
            language="en",
        )
        self.assertEqual(metadata.run_id, "run-1")


if __name__ == "__main__":
    unittest.main()

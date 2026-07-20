from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REMOTE_E2E = REPOSITORY_ROOT / "validation" / "remote_e2e"
SMOKE_VALIDATION = REPOSITORY_ROOT / "validation" / "smoke"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(REMOTE_E2E))
sys.path.insert(0, str(SMOKE_VALIDATION))

from pinn_strategy_system.application import (  # noqa: E402
    OperationOutcome,
    OperatorApplicationService,
)
from pinn_strategy_system.contracts import WikiPublicationSpec  # noqa: E402
from pinn_strategy_system.retrieval import FilesystemKnowledgeSource  # noqa: E402
from run_remote_full_chain import (  # noqa: E402
    PUBLISHED_WIKI_CHUNK,
    _assert_rag_results,
    _build_operator_case,
    _poisson_governance_gates,
    _write_fixture_documents,
)
from pinn_strategy_system.retrieval import (  # noqa: E402
    QWEN3_EMBEDDING_MODEL_ID,
    QWEN3_EMBEDDING_REVISION,
    QWEN3_RERANKER_MODEL_ID,
    QWEN3_RERANKER_REVISION,
)
from run_governed_pinn_smoke import _build_local_backend  # noqa: E402


class RemoteEndToEndContractTests(unittest.TestCase):
    def test_remote_poisson_case_passes_audit_without_backend_access(self) -> None:
        publication = WikiPublicationSpec(
            wiki_id="peer-pinn-localized-collocation",
            published_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
            project_id="universal-pinn-strategy-system",
            repo_commit="a" * 40,
            model_family="PINN",
            pde_family="cross-domain",
            task_type="strategy-optimization",
            language="en",
        )
        case = _build_operator_case(
            repo_commit="a" * 40,
            source_archive_sha256="b" * 64,
            publication=publication,
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_path = root / "case.json"
            case_path.write_text(case.model_dump_json(indent=2), encoding="utf-8")

            def forbidden_backend(_):
                raise AssertionError("read-only audit must not load an execution backend")

            result = OperatorApplicationService(
                runtime_root=(root / "runtime").resolve(),
                backend_factory=forbidden_backend,
            ).audit(case=case, case_path=case_path)

        self.assertEqual(result.outcome, OperationOutcome.SUCCESS)

    def test_frozen_rag_corpus_is_rebuildable_with_explicit_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            knowledge = Path(temporary).resolve()
            _write_fixture_documents(
                knowledge_root=knowledge,
                project_id="universal-pinn-strategy-system",
                repo_commit="a" * 40,
                valid_from=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
            )
            documents = FilesystemKnowledgeSource(knowledge).load_documents()

        self.assertEqual(len(documents), 15)
        self.assertTrue(
            all(item.chunk.metadata.model_family == "PINN" for item in documents)
        )
        self.assertEqual(
            {item.chunk.metadata.document_type for item in documents},
            {"HANDBOOK"},
        )

    def test_remote_rag_assertion_uses_production_active_index_schema(self) -> None:
        advisory = {
            "outcome": "SUCCESS",
            "data": {
                "evidence": [
                    {
                        "evidence_id": PUBLISHED_WIKI_CHUNK,
                        "reranker_model_id": QWEN3_RERANKER_MODEL_ID,
                        "reranker_model_revision": QWEN3_RERANKER_REVISION,
                    }
                ],
                "active_index": {
                    "active": {
                        "embedding_model_id": QWEN3_EMBEDDING_MODEL_ID,
                        "embedding_revision": QWEN3_EMBEDDING_REVISION,
                    }
                },
            },
        }
        conflict = {
            "data": {
                "conflicts": [{"claim_key": "radiation_temperature_unit"}],
                "decision_safe": False,
            }
        }

        _assert_rag_results(
            query_payload=advisory,
            conflict_payload=conflict,
        )

    def test_rejected_poisson_candidate_is_a_complete_governance_outcome(self) -> None:
        report = {
            "baseline": {"status": "RESULT_VALID"},
            "comparison": {"status": "RESULT_VALID"},
            "smoke": {"status": "PASS"},
            "decision": {"status": "REJECT"},
            "validation": {"status": "RESULT_INVALID"},
            "evidence_integrity": {"status": "PASS"},
            "replay": {"status": "PASS"},
            "provenance": {"status": "PASS", "worker_unchanged": True},
        }

        gates = _poisson_governance_gates(
            report,
            {"status": "PASS"},
        )

        self.assertTrue(all(gates.values()))
        report["decision"]["status"] = "NEEDS_EVIDENCE"
        self.assertFalse(
            all(
                _poisson_governance_gates(
                    report,
                    {"status": "PASS"},
                ).values()
            )
        )

    @unittest.skipIf(os.name == "nt", "virtualenv launchers are symlinks on Linux")
    def test_local_backend_preserves_virtualenv_launcher_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            interpreter = root / "base-python"
            interpreter.write_text("placeholder", encoding="utf-8")
            interpreter.chmod(0o755)
            launcher = root / "venv" / "bin" / "python"
            launcher.parent.mkdir(parents=True)
            launcher.symlink_to(interpreter)
            run_root = root / "runs"
            run_root.mkdir()

            with mock.patch.object(sys, "executable", str(launcher)):
                backend = _build_local_backend(run_root)

            self.assertEqual(
                backend._config.launcher_interpreter,
                launcher.absolute(),
            )
            self.assertNotEqual(
                backend._config.launcher_interpreter,
                launcher.resolve(strict=True),
            )


if __name__ == "__main__":
    unittest.main()

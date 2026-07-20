from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.assurance import KnowledgeGovernanceService  # noqa: E402
from pinn_strategy_system.cli import main  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactRef,
    ClaimScope,
    EvidenceLevel,
    KnowledgeValidity,
    ResultStatus,
    ValidationReport,
    WikiPublicationSpec,
)
from pinn_strategy_system.retrieval import IndexedKnowledgeDocument  # noqa: E402
from pinn_strategy_system.storage import (  # noqa: E402
    PublishedWikiStore,
    WikiPublicationConflictError,
)


NOW = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)


def _artifact(root: Path, name: str) -> ArtifactRef:
    path = root / f"{name}.json"
    content = json.dumps({"artifact": name}, sort_keys=True).encode("utf-8")
    path.write_bytes(content)
    return ArtifactRef(
        artifact_id=name,
        uri=path.as_uri(),
        sha256=hashlib.sha256(content).hexdigest(),
        media_type="application/json",
        size_bytes=len(content),
    )


def _candidate(root: Path):
    artifacts = {
        name: _artifact(root, name)
        for name in (
            "source",
            "dataset",
            "environment",
            "metrics",
            "physical",
            "reproducibility",
            "validation",
        )
    }
    validation = ValidationReport(
        report_id="wiki-validation",
        subject_id="wiki-run",
        status=ResultStatus.VALID,
        checks={"physics": True, "metrics": True, "provenance": True},
        evidence_refs=(artifacts["validation"],),
    )
    candidate = KnowledgeGovernanceService().create_wiki_candidate(
        candidate_id="wiki-candidate",
        title="Validated localized PINN evidence",
        conclusion=(
            "Localized diagnosis is reusable, while optimization acceptance "
            "remains case-specific."
        ),
        run_id="wiki-run",
        source_snapshot_ref=artifacts["source"],
        dataset_refs=(artifacts["dataset"],),
        environment_ref=artifacts["environment"],
        metric_report_ref=artifacts["metrics"],
        physical_audit_ref=artifacts["physical"],
        reproducibility_report_ref=artifacts["reproducibility"],
        validation_report=validation,
        validation_report_ref=artifacts["validation"],
        evidence_level=EvidenceLevel.SCIENTIFIC,
        claim_scope=ClaimScope.SCIENTIFIC_EFFECTIVENESS,
    )
    return candidate, artifacts


def _approval(
    *,
    kind: ApprovalKind = ApprovalKind.KNOWLEDGE_PROMOTION,
    scope: str = "wiki:wiki-candidate",
) -> ApprovalRecord:
    return ApprovalRecord(
        approval_id="wiki-human-approval",
        workflow_id="wiki-publication-workflow",
        kind=kind,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=NOW,
        scope=scope,
    )


def _publication(
    *,
    wiki_id: str = "localized-pinn-evidence",
    published_at: datetime = NOW + timedelta(minutes=1),
) -> WikiPublicationSpec:
    return WikiPublicationSpec(
        wiki_id=wiki_id,
        published_at=published_at,
        project_id="universal-pinn-strategy-system",
        repo_commit="a" * 40,
        model_family="PINN",
        pde_family="cross-domain",
        task_type="strategy-optimization",
        output_channels=("u",),
        dimensional_signatures=("case-defined",),
        failure_signatures=("localized-max-abs",),
        framework="PyTorch",
        language="en",
        claims={"decision_authority": "case-specific metric contract"},
    )


def _entry(root: Path, **publication_updates):
    candidate, artifacts = _candidate(root)
    publication = _publication(**publication_updates)
    entry = KnowledgeGovernanceService().publish_wiki(
        candidate=candidate,
        approval=_approval(),
        publication=publication,
    )
    return entry, artifacts


class WikiPublicationTests(unittest.TestCase):
    def test_contract_rejects_wrong_approval_scope_kind_and_time(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate, _ = _candidate(root)
            service = KnowledgeGovernanceService()
            cases = (
                (
                    _approval(kind=ApprovalKind.SKILL_PROMOTION),
                    _publication(),
                    "KNOWLEDGE_PROMOTION",
                ),
                (
                    _approval(scope="wiki:another-candidate"),
                    _publication(),
                    "scope",
                ),
                (
                    _approval(),
                    _publication(published_at=NOW - timedelta(seconds=1)),
                    "precede",
                ),
            )
            for approval, publication, message in cases:
                with self.subTest(message=message):
                    with self.assertRaisesRegex(ValidationError, message):
                        service.publish_wiki(
                            candidate=candidate,
                            approval=approval,
                            publication=publication,
                        )

    def test_contract_rejects_non_active_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            candidate, _ = _candidate(Path(temporary))
            superseded = candidate.model_copy(
                update={"validity_status": KnowledgeValidity.SUPERSEDED}
            )
            with self.assertRaisesRegex(ValidationError, "active Wiki candidate"):
                KnowledgeGovernanceService().publish_wiki(
                    candidate=superseded,
                    approval=_approval(),
                    publication=_publication(),
                )

    def test_atomic_publish_emits_rag_document_and_idempotent_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence"
            knowledge = root / "knowledge"
            evidence.mkdir()
            knowledge.mkdir()
            entry, _ = _entry(evidence)
            store = PublishedWikiStore(knowledge)

            first = store.publish(entry)
            second = store.publish(entry)
            target = knowledge / "wiki" / "localized-pinn-evidence" / "v0001"

            self.assertFalse(first.idempotent_replay)
            self.assertTrue(second.idempotent_replay)
            self.assertEqual(
                {path.name for path in target.iterdir()},
                {
                    "publication.json",
                    "entry.md",
                    "entry.index.json",
                    "manifest.json",
                },
            )
            indexed = IndexedKnowledgeDocument.model_validate_json(
                (target / "entry.index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(indexed.chunk.metadata.document_type, "WIKI")
            self.assertEqual(indexed.chunk.metadata.validation_status, "APPROVED")
            self.assertEqual(
                indexed.claims[0].value,
                "case-specific metric contract",
            )
            before = (target / "publication.json").read_bytes()
            self.assertEqual(
                hashlib.sha256(before).hexdigest(),
                first.publication_ref.sha256,
            )

    def test_conflict_path_escape_and_evidence_tamper_never_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence"
            knowledge = root / "knowledge"
            evidence.mkdir()
            knowledge.mkdir()
            entry, artifacts = _entry(evidence)
            store = PublishedWikiStore(knowledge)
            first = store.publish(entry)
            publication_path = Path(first.publication_ref.uri.removeprefix("file:///"))
            original = (knowledge / "wiki" / "localized-pinn-evidence" / "v0001" / "publication.json").read_bytes()

            changed_candidate = entry.candidate.model_copy(
                update={"conclusion": "A conflicting conclusion must not overwrite."}
            )
            changed = entry.model_copy(update={"candidate": changed_candidate})
            with self.assertRaisesRegex(
                WikiPublicationConflictError,
                "content conflicts",
            ):
                store.publish(changed)
            self.assertEqual(
                (knowledge / "wiki" / "localized-pinn-evidence" / "v0001" / "publication.json").read_bytes(),
                original,
            )

            escaped, _ = _entry(evidence, wiki_id="../escaped")
            with self.assertRaisesRegex(ValueError, "safe path segment"):
                store.publish(escaped)

            Path(artifacts["metrics"].uri.removeprefix("file:///")).write_text(
                "tampered",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                PublishedWikiStore(knowledge).publish(entry)

    def test_cli_publishes_and_then_verifies_without_skill_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence"
            knowledge = root / "knowledge"
            runtime = root / "runtime"
            evidence.mkdir()
            knowledge.mkdir()
            candidate, _ = _candidate(evidence)
            candidate_path = root / "candidate.json"
            approval_path = root / "approval.json"
            publication_path = root / "publication.json"
            candidate_path.write_text(
                candidate.model_dump_json(indent=2),
                encoding="utf-8",
            )
            approval_path.write_text(
                _approval().model_dump_json(indent=2),
                encoding="utf-8",
            )
            publication_path.write_text(
                _publication().model_dump_json(indent=2),
                encoding="utf-8",
            )

            first = self._invoke_cli(
                runtime,
                knowledge,
                candidate_path,
                approval_path,
                publication_path,
            )
            second = self._invoke_cli(
                runtime,
                knowledge,
                candidate_path,
                approval_path,
                publication_path,
            )

            self.assertEqual(first[0], 0)
            self.assertEqual(first[1]["code"], "WIKI_PUBLISHED")
            self.assertFalse(first[1]["data"]["skill_published"])
            self.assertEqual(second[0], 0)
            self.assertEqual(second[1]["code"], "WIKI_VERIFIED")

    @staticmethod
    def _invoke_cli(
        runtime: Path,
        knowledge: Path,
        candidate: Path,
        approval: Path,
        publication: Path,
    ) -> tuple[int, dict]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(
                [
                    "wiki",
                    "publish",
                    "--runtime-root",
                    str(runtime),
                    "--candidate",
                    str(candidate),
                    "--approval",
                    str(approval),
                    "--publication",
                    str(publication),
                    "--knowledge-root",
                    str(knowledge),
                    "--json",
                ]
            )
        return code, json.loads(output.getvalue())


if __name__ == "__main__":
    unittest.main()

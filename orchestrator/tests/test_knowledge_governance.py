from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.assurance import KnowledgeGovernanceService  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactRef,
    ClaimScope,
    DecisionRecord,
    DecisionStatus,
    EvidenceLevel,
    KnowledgeValidity,
    ResultStatus,
    ValidationReport,
)

SHA = "5" * 64


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://knowledge/{name}",
        sha256=SHA,
    )


def validation(run_id: str, valid: bool = True) -> ValidationReport:
    return ValidationReport(
        report_id=f"validation-{run_id}",
        subject_id=run_id,
        status=ResultStatus.VALID if valid else ResultStatus.INVALID,
        checks={"metrics": valid, "artifacts": valid, "physics": valid},
        evidence_refs=(artifact(f"evidence-{run_id}"),),
    )


def accepted_comparison(status: DecisionStatus = DecisionStatus.ACCEPT):
    return DecisionRecord(
        decision_id=f"comparison-{status.value.lower()}",
        status=status,
        observed_failure_mechanism="Localized boundary error",
        selected_intervention=(
            "Use the isolated candidate tactic"
            if status is DecisionStatus.ACCEPT
            else None
        ),
        unchanged_controls=("physics", "data", "budget"),
        expected_primary_metric_movement={"max_abs": "decrease"},
        guardrail_limits={"rmse": 1.0},
        falsification_condition="max_abs does not improve",
        rollback_plan="retain the baseline",
    )


def wiki(service: KnowledgeGovernanceService):
    return service.create_wiki_candidate(
        candidate_id="wiki-1",
        title="Smoke workflow evidence",
        conclusion="The governed workflow completed its declared smoke checks.",
        run_id="run-1",
        source_snapshot_ref=artifact("source"),
        dataset_refs=(artifact("dataset"),),
        environment_ref=artifact("environment"),
        metric_report_ref=artifact("metrics"),
        physical_audit_ref=artifact("physical"),
        reproducibility_report_ref=artifact("reproducibility"),
        validation_report=validation("run-1"),
        validation_report_ref=artifact("validation-run-1"),
        evidence_level=EvidenceLevel.SMOKE,
        claim_scope=ClaimScope.WORKFLOW_ONLY,
    )


class KnowledgeGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = KnowledgeGovernanceService()

    def test_invalid_run_cannot_create_wiki_candidate(self) -> None:
        with self.assertRaisesRegex(ValueError, "fully validated"):
            self.service.create_wiki_candidate(
                candidate_id="wiki-invalid",
                title="Invalid",
                conclusion="Must not publish.",
                run_id="run-invalid",
                source_snapshot_ref=artifact("source"),
                dataset_refs=(artifact("dataset"),),
                environment_ref=artifact("environment"),
                metric_report_ref=artifact("metrics"),
                physical_audit_ref=artifact("physical"),
                reproducibility_report_ref=artifact("reproducibility"),
                validation_report=validation("run-invalid", valid=False),
                validation_report_ref=artifact("validation-invalid"),
                evidence_level=EvidenceLevel.SCIENTIFIC,
                claim_scope=ClaimScope.SCIENTIFIC_EFFECTIVENESS,
            )

    def test_smoke_cannot_claim_scientific_effectiveness(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.create_wiki_candidate(
                candidate_id="wiki-overclaim",
                title="Overclaim",
                conclusion="This model is scientifically superior.",
                run_id="run-1",
                source_snapshot_ref=artifact("source"),
                dataset_refs=(artifact("dataset"),),
                environment_ref=artifact("environment"),
                metric_report_ref=artifact("metrics"),
                physical_audit_ref=artifact("physical"),
                reproducibility_report_ref=artifact("reproducibility"),
                validation_report=validation("run-1"),
                validation_report_ref=artifact("validation-run-1"),
                evidence_level=EvidenceLevel.SMOKE,
                claim_scope=ClaimScope.SCIENTIFIC_EFFECTIVENESS,
            )

    def test_supersession_increments_version_without_mutating_original(self) -> None:
        previous = wiki(self.service)
        transition = self.service.supersede_wiki(
            previous=previous,
            candidate_id="wiki-2",
            conclusion="A later validated run supersedes the earlier observation.",
            validation_report=validation("run-2"),
            validation_report_ref=artifact("validation-run-2"),
            metric_report_ref=artifact("metrics-run-2"),
            physical_audit_ref=artifact("physical-run-2"),
            reproducibility_report_ref=artifact("repro-run-2"),
            run_id="run-2",
            source_snapshot_ref=artifact("source-run-2"),
            dataset_refs=(artifact("dataset-run-2"),),
            environment_ref=artifact("environment-run-2"),
        )
        self.assertEqual(previous.validity_status, KnowledgeValidity.CANDIDATE)
        self.assertEqual(
            transition.previous.validity_status,
            KnowledgeValidity.SUPERSEDED,
        )
        self.assertEqual(transition.current.version, 2)
        self.assertEqual(transition.current.supersedes, ("wiki-1",))
        self.assertEqual(
            transition.current.source_snapshot_ref.artifact_id,
            "source-run-2",
        )

    def test_invalidation_is_append_only_evidence(self) -> None:
        previous = wiki(self.service)
        record = self.service.invalidate_wiki(
            record_id="invalidation-1",
            previous=previous,
            reason="Reference dataset provenance was withdrawn.",
            evidence_ref=artifact("withdrawal-evidence"),
            invalidated_at=datetime(2026, 7, 15, tzinfo=UTC),
        )
        self.assertEqual(record.candidate_id, previous.candidate_id)
        self.assertEqual(previous.validity_status, KnowledgeValidity.CANDIDATE)

    def test_skill_candidate_requires_two_validated_independent_runs(self) -> None:
        candidate = self.service.create_skill_candidate(
            candidate_id="skill-1",
            pattern_key="localized-roi-sampling-v1",
            title="Localized ROI sampling candidate",
            statement="Repeated validated runs suggest an ROI sampling tactic.",
            run_ids=("run-1", "run-2"),
            validation_reports=(validation("run-1"), validation("run-2")),
            evidence_refs=(artifact("run-1"), artifact("run-2")),
        )
        self.assertEqual(candidate.repeated_validated_pattern_count, 2)
        self.assertTrue(candidate.human_approval_required)

        with self.assertRaisesRegex(ValueError, "independent"):
            self.service.create_skill_candidate(
                candidate_id="skill-duplicate",
                pattern_key="localized-roi-sampling-v1",
                title="Duplicate run",
                statement="The same run cannot prove repetition.",
                run_ids=("run-1", "run-1"),
                validation_reports=(validation("run-1"), validation("run-1")),
                evidence_refs=(artifact("run-1"),),
            )

        with self.assertRaisesRegex(ValueError, "subject_id"):
            self.service.create_skill_candidate(
                candidate_id="skill-crossed-reports",
                pattern_key="localized-roi-sampling-v1",
                title="Crossed reports",
                statement="Reports must match their declared runs.",
                run_ids=("run-1", "run-2"),
                validation_reports=(validation("run-2"), validation("run-1")),
                evidence_refs=(artifact("run-1"), artifact("run-2")),
            )

    def test_skill_promotion_requires_isolated_replay_and_scoped_approval(self) -> None:
        candidate = self.service.create_skill_candidate(
            candidate_id="skill-replay",
            pattern_key="localized-roi-sampling-v1",
            title="Localized ROI sampling candidate",
            statement="Repeated validated runs suggest an ROI sampling tactic.",
            run_ids=("run-1", "run-2"),
            validation_reports=(validation("run-1"), validation("run-2")),
            evidence_refs=(artifact("run-1"), artifact("run-2")),
        )
        replay = self.service.evaluate_skill_replay(
            report_id="replay-report-1",
            candidate=candidate,
            baseline_run_id="baseline-3",
            replay_run_id="replay-3",
            isolation_environment_ref=artifact("isolated-environment"),
            baseline_validation_report=validation("baseline-3"),
            baseline_validation_ref=artifact("baseline-validation"),
            replay_validation_report=validation("replay-3"),
            replay_validation_ref=artifact("replay-validation"),
            comparison_decision=accepted_comparison(),
            isolation_verified=True,
        )
        approval = ApprovalRecord(
            approval_id="approval-skill-replay",
            workflow_id="workflow-knowledge",
            kind=ApprovalKind.SKILL_PROMOTION,
            decision=ApprovalDecision.APPROVED,
            approved_by="human-reviewer",
            approved_at=datetime(2026, 7, 16, tzinfo=UTC),
            scope="skill:skill-replay",
            evidence_refs=(artifact("replay-report"),),
        )
        published = self.service.promote_skill(
            skill_id="published-skill-1",
            version=1,
            candidate=candidate,
            replay_report=replay,
            approval=approval,
        )
        self.assertEqual(published.candidate.candidate_id, "skill-replay")
        self.assertEqual(published.version, 1)

    def test_failed_replay_or_wrong_approval_scope_cannot_publish_skill(self) -> None:
        candidate = self.service.create_skill_candidate(
            candidate_id="skill-blocked",
            pattern_key="localized-roi-sampling-v1",
            title="Blocked Skill",
            statement="This candidate still needs a passing replay.",
            run_ids=("run-1", "run-2"),
            validation_reports=(validation("run-1"), validation("run-2")),
            evidence_refs=(artifact("run-1"), artifact("run-2")),
        )
        failed_replay = self.service.evaluate_skill_replay(
            report_id="replay-failed",
            candidate=candidate,
            baseline_run_id="baseline-4",
            replay_run_id="replay-4",
            isolation_environment_ref=artifact("isolated-environment"),
            baseline_validation_report=validation("baseline-4"),
            baseline_validation_ref=artifact("baseline-validation"),
            replay_validation_report=validation("replay-4"),
            replay_validation_ref=artifact("replay-validation"),
            comparison_decision=accepted_comparison(DecisionStatus.REJECT),
            isolation_verified=True,
        )
        wrong_scope = ApprovalRecord(
            approval_id="approval-wrong-scope",
            workflow_id="workflow-knowledge",
            kind=ApprovalKind.SKILL_PROMOTION,
            decision=ApprovalDecision.APPROVED,
            approved_by="human-reviewer",
            approved_at=datetime(2026, 7, 16, tzinfo=UTC),
            scope="skill:another-candidate",
        )
        with self.assertRaisesRegex(ValueError, "valid replay"):
            self.service.promote_skill(
                skill_id="must-not-publish",
                version=1,
                candidate=candidate,
                replay_report=failed_replay,
                approval=wrong_scope,
            )

        valid_replay = self.service.evaluate_skill_replay(
            report_id="replay-valid-wrong-scope",
            candidate=candidate,
            baseline_run_id="baseline-5",
            replay_run_id="replay-5",
            isolation_environment_ref=artifact("isolated-environment"),
            baseline_validation_report=validation("baseline-5"),
            baseline_validation_ref=artifact("baseline-validation"),
            replay_validation_report=validation("replay-5"),
            replay_validation_ref=artifact("replay-validation"),
            comparison_decision=accepted_comparison(),
            isolation_verified=True,
        )
        with self.assertRaisesRegex(ValueError, "scope"):
            self.service.promote_skill(
                skill_id="must-not-publish-wrong-scope",
                version=1,
                candidate=candidate,
                replay_report=valid_replay,
                approval=wrong_scope,
            )

        with self.assertRaisesRegex(ValueError, "independent"):
            self.service.evaluate_skill_replay(
                report_id="replay-not-independent",
                candidate=candidate,
                baseline_run_id="baseline-6",
                replay_run_id="run-1",
                isolation_environment_ref=artifact("isolated-environment"),
                baseline_validation_report=validation("baseline-6"),
                baseline_validation_ref=artifact("baseline-validation"),
                replay_validation_report=validation("run-1"),
                replay_validation_ref=artifact("replay-validation"),
                comparison_decision=accepted_comparison(),
                isolation_verified=True,
            )


if __name__ == "__main__":
    unittest.main()

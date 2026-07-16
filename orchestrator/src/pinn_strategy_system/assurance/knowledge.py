"""Append-only Wiki versioning and repeated-pattern Skill candidacy."""

from __future__ import annotations

from datetime import datetime

from pinn_strategy_system.contracts import (
    ApprovalRecord,
    ArtifactRef,
    ClaimScope,
    EvidenceLevel,
    KnowledgeCandidate,
    KnowledgeKind,
    KnowledgeValidity,
    KnowledgeVersionTransition,
    DecisionRecord,
    DecisionStatus,
    PublishedSkill,
    ResultStatus,
    SkillReplayReport,
    ValidationReport,
    WikiEntryCandidate,
    WikiInvalidationRecord,
)


class KnowledgeGovernanceService:
    def create_wiki_candidate(
        self,
        *,
        candidate_id: str,
        title: str,
        conclusion: str,
        run_id: str,
        source_snapshot_ref: ArtifactRef,
        dataset_refs: tuple[ArtifactRef, ...],
        environment_ref: ArtifactRef,
        metric_report_ref: ArtifactRef,
        physical_audit_ref: ArtifactRef,
        reproducibility_report_ref: ArtifactRef,
        validation_report: ValidationReport,
        validation_report_ref: ArtifactRef,
        evidence_level: EvidenceLevel,
        claim_scope: ClaimScope,
        version: int = 1,
        supersedes: tuple[str, ...] = (),
    ) -> WikiEntryCandidate:
        _require_validated(validation_report)
        return WikiEntryCandidate(
            candidate_id=candidate_id,
            version=version,
            title=title,
            conclusion=conclusion,
            run_id=run_id,
            source_snapshot_ref=source_snapshot_ref,
            dataset_refs=dataset_refs,
            environment_ref=environment_ref,
            metric_report_ref=metric_report_ref,
            physical_audit_ref=physical_audit_ref,
            reproducibility_report_ref=reproducibility_report_ref,
            validation_report_ref=validation_report_ref,
            evidence_level=evidence_level,
            claim_scope=claim_scope,
            supersedes=supersedes,
        )

    def supersede_wiki(
        self,
        *,
        previous: WikiEntryCandidate,
        candidate_id: str,
        conclusion: str,
        validation_report: ValidationReport,
        validation_report_ref: ArtifactRef,
        metric_report_ref: ArtifactRef,
        physical_audit_ref: ArtifactRef,
        reproducibility_report_ref: ArtifactRef,
        run_id: str,
        source_snapshot_ref: ArtifactRef,
        dataset_refs: tuple[ArtifactRef, ...],
        environment_ref: ArtifactRef,
    ) -> KnowledgeVersionTransition:
        current = self.create_wiki_candidate(
            candidate_id=candidate_id,
            title=previous.title,
            conclusion=conclusion,
            run_id=run_id,
            source_snapshot_ref=source_snapshot_ref,
            dataset_refs=dataset_refs,
            environment_ref=environment_ref,
            metric_report_ref=metric_report_ref,
            physical_audit_ref=physical_audit_ref,
            reproducibility_report_ref=reproducibility_report_ref,
            validation_report=validation_report,
            validation_report_ref=validation_report_ref,
            evidence_level=previous.evidence_level,
            claim_scope=previous.claim_scope,
            version=previous.version + 1,
            supersedes=(previous.candidate_id,),
        )
        previous_payload = previous.model_dump(mode="json")
        previous_payload["validity_status"] = KnowledgeValidity.SUPERSEDED.value
        return KnowledgeVersionTransition(
            previous=WikiEntryCandidate.model_validate(previous_payload),
            current=current,
        )

    def invalidate_wiki(
        self,
        *,
        record_id: str,
        previous: WikiEntryCandidate,
        reason: str,
        evidence_ref: ArtifactRef,
        invalidated_at: datetime,
    ) -> WikiInvalidationRecord:
        if previous.validity_status in {
            KnowledgeValidity.SUPERSEDED,
            KnowledgeValidity.INVALIDATED,
        }:
            raise ValueError("only an active Wiki version can be invalidated")
        return WikiInvalidationRecord(
            record_id=record_id,
            candidate_id=previous.candidate_id,
            invalidated_version=previous.version,
            reason=reason,
            evidence_ref=evidence_ref,
            invalidated_at=invalidated_at,
        )

    def create_skill_candidate(
        self,
        *,
        candidate_id: str,
        pattern_key: str,
        title: str,
        statement: str,
        run_ids: tuple[str, ...],
        validation_reports: tuple[ValidationReport, ...],
        evidence_refs: tuple[ArtifactRef, ...],
    ) -> KnowledgeCandidate:
        if len(set(run_ids)) < 2:
            raise ValueError("SkillCandidate requires at least two independent runs")
        if len(validation_reports) != len(run_ids):
            raise ValueError("every SkillCandidate run requires a validation report")
        for run_id, report in zip(run_ids, validation_reports, strict=True):
            _require_validated(report)
            if report.subject_id != run_id:
                raise ValueError("validation report subject_id must match its run_id")
        return KnowledgeCandidate(
            candidate_id=candidate_id,
            kind=KnowledgeKind.SKILL,
            title=title,
            statement=statement,
            evidence_refs=evidence_refs,
            run_ids=run_ids,
            validation_status=ResultStatus.VALID,
            pattern_key=pattern_key,
            repeated_validated_pattern_count=len(set(run_ids)),
        )

    def evaluate_skill_replay(
        self,
        *,
        report_id: str,
        candidate: KnowledgeCandidate,
        baseline_run_id: str,
        replay_run_id: str,
        isolation_environment_ref: ArtifactRef,
        baseline_validation_report: ValidationReport,
        baseline_validation_ref: ArtifactRef,
        replay_validation_report: ValidationReport,
        replay_validation_ref: ArtifactRef,
        comparison_decision: DecisionRecord,
        isolation_verified: bool,
    ) -> SkillReplayReport:
        if candidate.kind is not KnowledgeKind.SKILL:
            raise ValueError("only Skill candidates can enter replay")
        if candidate.validation_status is not ResultStatus.VALID:
            raise ValueError("Skill replay requires a validated candidate")
        if replay_run_id in candidate.run_ids:
            raise ValueError("Skill replay run must be independent from source runs")
        _require_validated(baseline_validation_report)
        _require_validated(replay_validation_report)
        if baseline_validation_report.subject_id != baseline_run_id:
            raise ValueError("baseline validation must match baseline_run_id")
        if replay_validation_report.subject_id != replay_run_id:
            raise ValueError("replay validation must match replay_run_id")
        checks = {
            "candidate_validated": True,
            "independent_replay": replay_run_id not in candidate.run_ids,
            "isolated_environment": isolation_verified,
            "baseline_validated": True,
            "replay_validated": True,
            "baseline_comparison_accepts": (
                comparison_decision.status is DecisionStatus.ACCEPT
            ),
        }
        status = (
            ResultStatus.VALID
            if all(checks.values())
            else ResultStatus.INVALID
        )
        return SkillReplayReport(
            report_id=report_id,
            candidate_id=candidate.candidate_id,
            baseline_run_id=baseline_run_id,
            replay_run_id=replay_run_id,
            isolation_environment_ref=isolation_environment_ref,
            baseline_validation_ref=baseline_validation_ref,
            replay_validation_ref=replay_validation_ref,
            comparison_decision=comparison_decision,
            checks=checks,
            status=status,
        )

    def promote_skill(
        self,
        *,
        skill_id: str,
        version: int,
        candidate: KnowledgeCandidate,
        replay_report: SkillReplayReport,
        approval: ApprovalRecord,
        supersedes: tuple[str, ...] = (),
    ) -> PublishedSkill:
        return PublishedSkill(
            skill_id=skill_id,
            version=version,
            candidate=candidate,
            replay_report=replay_report,
            approval=approval,
            supersedes=supersedes,
        )


def _require_validated(report: ValidationReport) -> None:
    if report.status is not ResultStatus.VALID or not all(report.checks.values()):
        raise ValueError("knowledge candidates require a fully validated report")

"""Completeness and single-intervention gates for experiment proposals."""

from __future__ import annotations

from pinn_strategy_system.contracts import (
    AuditStatus,
    ExperimentCompletenessReport,
    ExperimentDraft,
    ExperimentSpec,
)


class ExperimentGovernanceService:
    def audit(
        self,
        *,
        report_id: str,
        draft: ExperimentDraft,
    ) -> ExperimentCompletenessReport:
        checks = {
            "source_snapshot": draft.source_snapshot_ref is not None,
            "dataset_identity": bool(draft.dataset_refs),
            "environment": draft.environment_ref is not None,
            "random_seed": draft.random_seed is not None,
            "baseline": draft.baseline_run_ref is not None,
            "metric_contract": draft.metric_contract_ref is not None,
            "smoke_budget": draft.smoke_budget is not None,
            "full_budget": draft.full_budget is not None,
            "output_root": bool(draft.output_root),
            "checkpoint_policy": bool(draft.checkpoint_policy),
            "expected_artifacts": bool(draft.expected_artifacts),
            "rollback": bool(draft.rollback_plan),
            "failure_mechanism": bool(draft.observed_failure_mechanism),
            "supporting_evidence": bool(draft.supporting_evidence_refs),
            "expected_metric_movement": bool(
                draft.expected_primary_metric_movement
            ),
            "guardrail_limits": bool(draft.guardrail_limits),
            "falsification_condition": bool(draft.falsification_condition),
            "unchanged_controls": bool(draft.unchanged_controls),
            "single_intervention": len(draft.interventions) == 1,
        }
        missing = tuple(name for name, passed in checks.items() if not passed)
        if len(draft.interventions) > 1:
            return ExperimentCompletenessReport(
                report_id=report_id,
                status=AuditStatus.REJECT,
                checks=checks,
                missing_fields=missing,
                findings=(
                    "proposal changes more than one logical point and must be split",
                ),
            )
        if missing:
            return ExperimentCompletenessReport(
                report_id=report_id,
                status=AuditStatus.NEEDS_EVIDENCE,
                checks=checks,
                missing_fields=missing,
                findings=tuple(
                    f"required experiment evidence is missing: {name}"
                    for name in missing
                ),
            )

        spec = ExperimentSpec(
            experiment_id=draft.experiment_id,
            project_id=draft.project_id,
            observed_failure_mechanism=draft.observed_failure_mechanism,
            supporting_evidence_refs=draft.supporting_evidence_refs,
            single_intervention=draft.interventions[0],
            unchanged_controls=draft.unchanged_controls,
            expected_primary_metric_movement=(
                draft.expected_primary_metric_movement
            ),
            guardrail_limits=draft.guardrail_limits,
            smoke_budget=draft.smoke_budget,
            full_budget=draft.full_budget,
            falsification_condition=draft.falsification_condition,
            rollback_plan=draft.rollback_plan,
            source_snapshot_ref=draft.source_snapshot_ref,
            dataset_refs=draft.dataset_refs,
            environment_ref=draft.environment_ref,
            random_seed=draft.random_seed,
            baseline_run_ref=draft.baseline_run_ref,
            metric_contract_ref=draft.metric_contract_ref,
            output_root=draft.output_root,
            checkpoint_policy=draft.checkpoint_policy,
            expected_artifacts=draft.expected_artifacts,
        )
        return ExperimentCompletenessReport(
            report_id=report_id,
            status=AuditStatus.PASS,
            checks=checks,
            experiment_spec=spec,
        )

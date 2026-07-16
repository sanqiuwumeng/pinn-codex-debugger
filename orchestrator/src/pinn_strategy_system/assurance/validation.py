"""Independent scientific-result validity gate."""

from __future__ import annotations

from pinn_strategy_system.contracts import (
    AuditStatus,
    DecisionStatus,
    ResultStatus,
    RunValidationInput,
    ValidationReport,
)


class RunValidationService:
    def validate(
        self,
        *,
        report_id: str,
        validation_input: RunValidationInput,
    ) -> ValidationReport:
        missing_artifacts = tuple(
            name
            for name in validation_input.required_artifacts
            if name not in validation_input.produced_artifacts
        )
        checks = {
            "process_exit": validation_input.process_exit_code == 0,
            "physical_audit": (
                validation_input.physical_audit.status is AuditStatus.PASS
            ),
            "model_evaluation": (
                validation_input.model_evaluation.status
                is ResultStatus.VALID
            ),
            "metric_decision": (
                validation_input.metric_decision.status
                is DecisionStatus.ACCEPT
            ),
            "required_artifacts": not missing_artifacts,
            "source_snapshot": bool(validation_input.source_snapshot_ref.sha256),
            "dataset_identity": all(
                item.sha256 for item in validation_input.dataset_refs
            ),
            "environment": bool(validation_input.environment_ref.sha256),
            "run_manifest": bool(validation_input.run_manifest_ref.sha256),
            "random_seed": validation_input.random_seed >= 0,
        }
        findings = tuple(
            [
                f"validation check failed: {name}"
                for name, passed in checks.items()
                if not passed
            ]
            + [
                f"required artifact is missing: {name}"
                for name in missing_artifacts
            ]
        )
        evaluation = validation_input.model_evaluation
        evidence = (
            validation_input.run_manifest_ref,
            validation_input.source_snapshot_ref,
            *validation_input.dataset_refs,
            validation_input.environment_ref,
            *validation_input.produced_artifacts.values(),
            evaluation.physical_model_authority_ref,
            *evaluation.diagnostic_refs,
            *(
                (evaluation.prediction_analysis_ref,)
                if evaluation.prediction_analysis_ref is not None
                else ()
            ),
        )
        return ValidationReport(
            report_id=report_id,
            subject_id=validation_input.run_id,
            status=(
                ResultStatus.VALID
                if all(checks.values())
                else ResultStatus.INVALID
            ),
            checks=checks,
            findings=findings,
            evidence_refs=evidence,
        )

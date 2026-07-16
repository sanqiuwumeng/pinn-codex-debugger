from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.contracts import (  # noqa: E402
    AggregationPolicy,
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactRef,
    AuditStatus,
    BudgetSpec,
    DecisionRecord,
    DecisionStatus,
    ExperimentSpec,
    InterventionChange,
    KnowledgeCandidate,
    KnowledgeKind,
    LocalizedError,
    MetricContract,
    MetricDirection,
    MetricEvidenceBasis,
    MetricRole,
    MetricRule,
    ModelEvaluationReport,
    PhysicalAuditReport,
    PhysicalModelAuthority,
    PhysicalParameterInput,
    PhysicalParameterRecord,
    PredictionAnalysisReport,
    ReferenceEvidence,
    ReferenceKind,
    ResultStatus,
    RunEvent,
    RunEventType,
    RunManifest,
    SshConnectionProfile,
    SourceRef,
    SourceSnapshot,
    UnitSystemContract,
    ValidationReport,
    WorkflowIntent,
    WorkflowRequest,
    WorkflowStateEnvelope,
    validate_workflow_state,
)

SHA = "a" * 64


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://phase0/{name}",
        sha256=SHA,
        media_type="application/json",
    )


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SourceRef(
            uri="file:///project/config.json",
            sha256=SHA,
            line_start=1,
            line_end=4,
            symbol="rho",
        )
        self.request = WorkflowRequest(
            request_id="request-1",
            workflow_id="workflow-1",
            project_id="project-1",
            objective="Audit a PINN experiment before proposing one intervention.",
            intent=WorkflowIntent.READ_ONLY,
            snapshot_ref=artifact("snapshot"),
            requested_by="user",
        )
        self.metric_contract = MetricContract(
            contract_id="metrics-1",
            physical_model_authority_ref=artifact("model-authority"),
            reference_evidence_refs=(artifact("truth"),),
            metrics=(
                MetricRule(
                    name="rmse",
                    role=MetricRole.PRIMARY,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                ),
                MetricRule(
                    name="max_abs",
                    role=MetricRole.GUARDRAIL,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                    max_regression=0.0,
                    unit="K",
                ),
            ),
            primary_order=("rmse",),
            aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
            roi_labels=("case_roi",),
        )
        self.localized = LocalizedError(
            flat_index=0,
            coordinates={"t": 0.0, "x": 0.0, "channel": "temperature"},
            prediction=301.0,
            reference=300.0,
            signed_error=1.0,
            absolute_error=1.0,
            context={"region": "solid"},
        )
        self.prediction_report = PredictionAnalysisReport(
            report_id="prediction-1",
            status=ResultStatus.VALID,
            prediction_ref=artifact("prediction"),
            reference_ref=artifact("truth"),
            global_metrics={"mse": 1.0, "rmse": 1.0, "max_abs": 1.0},
            max_abs=self.localized,
            top_k=(self.localized,),
            alignment_checks={
                "reference_identity": True,
                "unit": True,
                "coordinate_system": True,
                "grid": True,
                "time": True,
                "normalization": True,
            },
        )

    def test_ssh_connection_profile_persists_fingerprints_only(self) -> None:
        profile = SshConnectionProfile(
            profile_id="autodl-a",
            host_key_fingerprint_sha256="b" * 64,
            identity_key_fingerprint_sha256="c" * 64,
        )

        payload = profile.model_dump(mode="json")

        self.assertEqual(payload["transport"], "system-openssh")
        self.assertFalse(
            {"hostname", "username", "port", "password", "identity_file"}
            & payload.keys()
        )

    def test_all_domain_contracts_round_trip_as_json(self) -> None:
        parameter_input = PhysicalParameterInput(
            parameter_id="density",
            symbol="rho",
            meaning="material density",
            quantity_kind="density",
            raw_value=4.43,
            raw_unit="g/cm^3",
            source_ref=self.source,
        )
        parameter_record = PhysicalParameterRecord(
            parameter_id="density",
            symbol="rho",
            meaning="material density",
            quantity_kind="density",
            unit_system_id="si-test-units",
            raw_value=4.43,
            raw_unit="g/cm^3",
            canonical_value=4430.0,
            canonical_unit="kg/m^3",
            dimensional_signature="[mass] / [length] ** 3",
            conversion_factor=1000.0,
            source_ref=self.source,
            confirmation_status=AuditStatus.PASS,
        )
        physical_report = PhysicalAuditReport(
            report_id="physical-1",
            unit_system_id="si-test-units",
            status=AuditStatus.PASS,
            parameter_records=(parameter_record,),
            derived_manifest_ref=artifact("canonical-parameters"),
        )
        unit_system = UnitSystemContract(
            unit_system_id="si-test-units",
            name="test-case SI units",
            quantity_units={"density": "kg/m^3", "temperature": "K"},
            source_refs=(self.source,),
            confirmed_by_user=True,
        )
        model_authority = PhysicalModelAuthority(
            authority_id="authority-1",
            project_id="project-1",
            model_family="pinn",
            pde_family="heat-equation",
            task_type="forward",
            governing_equation_refs=(self.source,),
            boundary_condition_refs=(self.source,),
            initial_condition_refs=(self.source,),
            output_channels=("temperature",),
            unit_system=unit_system,
            confirmed_by_user=True,
        )
        reference_evidence = ReferenceEvidence(
            reference_id="fem-test-reference",
            authority_id="authority-1",
            kind=ReferenceKind.NUMERICAL,
            artifact_ref=artifact("truth"),
            output_channels=("temperature",),
            coordinate_system="cartesian-xy",
            channel_units={"temperature": "K"},
            source_refs=(self.source,),
            test_case_only=True,
            limitations=("numerical test reference, not experimental truth",),
        )
        model_evaluation = ModelEvaluationReport(
            report_id="evaluation-1",
            status=ResultStatus.VALID,
            physical_model_authority_ref=artifact("model-authority"),
            metric_values={"rmse": 1.0, "max_abs": 1.0},
            metric_bases={
                "rmse": MetricEvidenceBasis.REFERENCE_EVIDENCE,
                "max_abs": MetricEvidenceBasis.REFERENCE_EVIDENCE,
            },
            prediction_analysis_ref=artifact("prediction-report"),
            domain_provider_ids=("heat-transfer.phase-change.v1",),
            checks={"authority_compatible": True, "reference_aligned": True},
        )
        experiment = ExperimentSpec(
            experiment_id="experiment-1",
            project_id="project-1",
            observed_failure_mechanism="A localized error persists near the phase band.",
            supporting_evidence_refs=(artifact("prediction-report"),),
            single_intervention=InterventionChange(
                target="sampling.roi_points",
                before=1000,
                after=1500,
                rationale="Increase sampling only inside the approved ROI.",
            ),
            unchanged_controls=("network", "optimizer", "loss weights"),
            expected_primary_metric_movement={"rmse": "decrease"},
            guardrail_limits={"max_abs": 0.0},
            smoke_budget=BudgetSpec(max_steps=10, max_seconds=30),
            full_budget=BudgetSpec(max_steps=1000, max_seconds=3600),
            falsification_condition="RMSE does not improve or max_abs regresses.",
            rollback_plan="Retain the baseline configuration.",
            source_snapshot_ref=artifact("source-snapshot"),
            dataset_refs=(artifact("dataset"),),
            environment_ref=artifact("training-environment"),
            random_seed=42,
            baseline_run_ref=artifact("baseline-run"),
            metric_contract_ref=artifact("metric-contract"),
            output_root="artifact://runs/experiment-1",
            checkpoint_policy="write at declared intervals",
            expected_artifacts=("metrics.json", "run_status.json"),
        )
        run = RunManifest(
            run_id="run-1",
            workflow_id="workflow-1",
            experiment_id="experiment-1",
            idempotency_key="experiment-1-smoke-1",
            environment_name="pytorch2.3.1",
            interpreter="C:/Users/Mli/.conda/envs/pytorch2.3.1/python.exe",
            working_directory="file:///project",
            command=("python", "run.py", "--smoke"),
            config_ref=artifact("staging-config"),
            output_root="artifact://runs/run-1",
            expected_artifacts=("run_status.json", "metrics.json"),
            checkpoint_policy="write before launch and at declared intervals",
            rollback_plan="Keep baseline active and preserve failed artifacts.",
        )
        timestamp = datetime(2026, 7, 15, tzinfo=UTC)
        models = (
            self.request,
            SourceSnapshot(
                snapshot_id="snapshot-1",
                project_id="project-1",
                root_uri="file:///project",
                created_at=timestamp,
                file_manifest_ref=artifact("file-manifest"),
                environment_ref=artifact("environment"),
            ),
            parameter_input,
            unit_system,
            model_authority,
            reference_evidence,
            physical_report,
            self.metric_contract,
            model_evaluation,
            experiment,
            run,
            RunEvent(
                event_id="event-1",
                run_id="run-1",
                event_type=RunEventType.RUN_QUEUED,
                occurred_at=timestamp,
                payload={"idempotency_key": "experiment-1-smoke-1"},
            ),
            self.prediction_report,
            ValidationReport(
                report_id="validation-1",
                subject_id="run-1",
                status=ResultStatus.VALID,
                checks={"artifacts": True, "metrics": True},
            ),
            DecisionRecord(
                decision_id="decision-1",
                status=DecisionStatus.ACCEPT,
                observed_failure_mechanism="localized sampling deficit",
                selected_intervention="increase ROI sampling",
                supporting_evidence_refs=(artifact("prediction-report"),),
            ),
            ApprovalRecord(
                approval_id="approval-1",
                workflow_id="workflow-1",
                kind=ApprovalKind.EXPERIMENT,
                decision=ApprovalDecision.APPROVED,
                approved_by="user",
                approved_at=timestamp,
                scope="experiment-1 smoke only",
            ),
            KnowledgeCandidate(
                candidate_id="wiki-1",
                kind=KnowledgeKind.WIKI,
                title="Validated localized sampling observation",
                statement="ROI sampling reduced error in a validated run.",
                evidence_refs=(artifact("validation"),),
                run_ids=("run-1",),
                validation_status=ResultStatus.VALID,
            ),
        )

        for model in models:
            encoded = model.model_dump_json()
            decoded = type(model).model_validate_json(encoded)
            self.assertEqual(model, decoded)
            self.assertEqual(json.loads(encoded)["schema_version"], "1.0")
            self.assertNotIn("pickle", encoded.casefold())

    def test_metric_contract_requires_explicit_scalar_authorization(self) -> None:
        with self.assertRaises(ValidationError):
            MetricContract(
                contract_id="metrics-scalar",
                physical_model_authority_ref=artifact("model-authority"),
                reference_evidence_refs=(artifact("truth"),),
                metrics=(
                    MetricRule(
                        name="rmse",
                        role=MetricRole.PRIMARY,
                        direction=MetricDirection.MINIMIZE,
                        evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                        weight=1.0,
                    ),
                ),
                primary_order=("rmse",),
                aggregation_policy=AggregationPolicy.SCALAR,
                scalar_aggregation_authorized=False,
            )

    def test_run_event_rejects_non_json_payload_objects(self) -> None:
        with self.assertRaises(ValidationError):
            RunEvent(
                event_id="event-non-json",
                run_id="run-1",
                event_type=RunEventType.METRIC_UPDATED,
                occurred_at=datetime(2026, 7, 15, tzinfo=UTC),
                payload={"opaque_object": object()},
            )

    def test_valid_prediction_report_requires_localization(self) -> None:
        with self.assertRaises(ValidationError):
            PredictionAnalysisReport(
                report_id="prediction-invalid-contract",
                status=ResultStatus.VALID,
                prediction_ref=artifact("prediction"),
                reference_ref=artifact("truth"),
                alignment_checks={"grid": True},
            )

    def test_skill_candidate_requires_repeated_validated_pattern(self) -> None:
        with self.assertRaises(ValidationError):
            KnowledgeCandidate(
                candidate_id="skill-1",
                kind=KnowledgeKind.SKILL,
                title="Premature skill",
                statement="One run is not a reusable pattern.",
                evidence_refs=(artifact("validation"),),
                validation_status=ResultStatus.VALID,
                repeated_validated_pattern_count=1,
            )

    def test_workflow_state_is_a_small_declared_json_projection(self) -> None:
        state = WorkflowStateEnvelope(
            workflow_id="workflow-1",
            request=self.request,
            physical_audit=PhysicalAuditReport(
                report_id="physical-1",
                unit_system_id="si-test-units",
                status=AuditStatus.PASS,
            ),
            metric_contract=self.metric_contract,
            model_evaluation=ModelEvaluationReport(
                report_id="evaluation-1",
                status=ResultStatus.VALID,
                physical_model_authority_ref=artifact("model-authority"),
                metric_values={"rmse": 1.0},
                metric_bases={
                    "rmse": MetricEvidenceBasis.REFERENCE_EVIDENCE,
                },
                prediction_analysis_ref=artifact("prediction-report"),
                checks={"authority_compatible": True},
            ),
            artifact_refs=(artifact("prediction"), artifact("truth")),
        ).to_state()

        normalized = validate_workflow_state(state)
        json.dumps(normalized, allow_nan=False)
        self.assertNotIn("weights", normalized)
        self.assertNotIn("arrays", normalized)

        with self.assertRaises(ValidationError):
            validate_workflow_state({**state, "model_weights": [1.0, 2.0]})


if __name__ == "__main__":
    unittest.main()

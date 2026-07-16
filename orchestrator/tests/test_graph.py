from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

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
    ExperimentSpec,
    InterventionChange,
    MetricContract,
    MetricDirection,
    MetricEvidenceBasis,
    MetricRole,
    MetricRule,
    ModelEvaluationReport,
    PhysicalAuditReport,
    ResultStatus,
    WorkflowIntent,
    WorkflowRequest,
    WorkflowStage,
    WorkflowStateEnvelope,
)
from pinn_strategy_system.orchestration import (  # noqa: E402
    PersistenceScope,
    build_phase0_graph,
    specialist_persistence,
)

SHA = "b" * 64
NOW = datetime(2026, 7, 15, tzinfo=UTC)


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://graph/{name}",
        sha256=SHA,
    )


def request(workflow_id: str, intent: WorkflowIntent) -> WorkflowRequest:
    return WorkflowRequest(
        request_id=f"request-{workflow_id}",
        workflow_id=workflow_id,
        project_id="project-1",
        objective="Complete assurance gates before any optimization action.",
        intent=intent,
        snapshot_ref=artifact("snapshot"),
        requested_by="user",
    )


def physical(status: AuditStatus = AuditStatus.PASS) -> PhysicalAuditReport:
    return PhysicalAuditReport(
        report_id="physical-1",
        unit_system_id="model-units",
        status=status,
    )


def metrics() -> MetricContract:
    return MetricContract(
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
    )


def evaluation(status: ResultStatus = ResultStatus.VALID) -> ModelEvaluationReport:
    return ModelEvaluationReport(
        report_id="evaluation-1",
        status=status,
        physical_model_authority_ref=artifact("model-authority"),
        metric_values=(
            {"rmse": 1.0, "max_abs": 1.0}
            if status is ResultStatus.VALID
            else {}
        ),
        metric_bases=(
            {
                "rmse": MetricEvidenceBasis.REFERENCE_EVIDENCE,
                "max_abs": MetricEvidenceBasis.REFERENCE_EVIDENCE,
            }
            if status is ResultStatus.VALID
            else {}
        ),
        prediction_analysis_ref=(
            artifact("prediction-report")
            if status is ResultStatus.VALID
            else None
        ),
        checks={"all": status is ResultStatus.VALID},
    )


def experiment() -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id="experiment-1",
        project_id="project-1",
        observed_failure_mechanism="localized residual hotspot",
        supporting_evidence_refs=(artifact("prediction-report"),),
        single_intervention=InterventionChange(
            target="sampling.roi_points",
            before=1000,
            after=1500,
            rationale="increase samples only in the hotspot ROI",
        ),
        unchanged_controls=("network", "optimizer", "loss weights"),
        expected_primary_metric_movement={"rmse": "decrease"},
        guardrail_limits={"max_abs": 0.0},
        smoke_budget=BudgetSpec(max_steps=10),
        full_budget=BudgetSpec(max_steps=1000),
        falsification_condition="RMSE does not improve or max_abs regresses.",
        rollback_plan="Keep the baseline configuration.",
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


def approval(
    workflow_id: str,
    kind: ApprovalKind,
    decision: ApprovalDecision = ApprovalDecision.APPROVED,
) -> ApprovalRecord:
    return ApprovalRecord(
        approval_id=f"approval-{workflow_id}-{kind.value}",
        workflow_id=workflow_id,
        kind=kind,
        decision=decision,
        approved_by="user",
        approved_at=NOW,
        scope=f"{workflow_id}:{kind.value}",
    )


def initial_state(
    workflow_id: str,
    intent: WorkflowIntent,
    *,
    include_physical: bool = False,
    include_metrics: bool = False,
    include_evaluation: bool = False,
    include_experiment: bool = False,
    smoke_status: ResultStatus = ResultStatus.NOT_EVALUATED,
):
    return WorkflowStateEnvelope(
        workflow_id=workflow_id,
        request=request(workflow_id, intent),
        physical_audit=physical() if include_physical else None,
        metric_contract=metrics() if include_metrics else None,
        model_evaluation=evaluation() if include_evaluation else None,
        experiment_spec=experiment() if include_experiment else None,
        approvals=(
            (approval(workflow_id, ApprovalKind.METRIC_PRIORITY),)
            if include_metrics
            else ()
        ),
        smoke_validation_status=smoke_status,
    ).to_state()


class GraphTests(unittest.TestCase):
    def test_sqlite_interrupts_survive_restart_and_resume_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            database = str(Path(temp) / "workflow.sqlite")
            config = {"configurable": {"thread_id": "workflow-1"}}

            with SqliteSaver.from_conn_string(database) as checkpointer:
                graph = build_phase0_graph(checkpointer)
                result = graph.invoke(
                    initial_state("workflow-1", WorkflowIntent.READ_ONLY),
                    config,
                )
                self.assertEqual(
                    result["stage"], WorkflowStage.NEEDS_UNIT_CONFIRMATION.value
                )
                self.assertTrue(result["__interrupt__"])

            with SqliteSaver.from_conn_string(database) as checkpointer:
                graph = build_phase0_graph(checkpointer)
                persisted = graph.get_state(config)
                self.assertEqual(
                    persisted.values["stage"],
                    WorkflowStage.NEEDS_UNIT_CONFIRMATION.value,
                )
                result = graph.invoke(
                    Command(
                        resume={
                            "physical_audit": physical().model_dump(mode="json")
                        }
                    ),
                    config,
                )
                self.assertEqual(
                    result["stage"], WorkflowStage.NEEDS_METRIC_PRIORITY.value
                )

                result = graph.invoke(
                    Command(
                        resume={
                            "metric_contract": metrics().model_dump(mode="json"),
                            "approval": approval(
                                "workflow-1", ApprovalKind.METRIC_PRIORITY
                            ).model_dump(mode="json"),
                        }
                    ),
                    config,
                )
                self.assertEqual(
                    result["stage"],
                    WorkflowStage.NEEDS_DIAGNOSTIC_EVIDENCE.value,
                )

                result = graph.invoke(
                    Command(
                        resume={
                            "model_evaluation": evaluation().model_dump(mode="json")
                        }
                    ),
                    config,
                )
                self.assertEqual(result["stage"], WorkflowStage.COMPLETED.value)
                self.assertEqual(
                    result["completed_nodes"].count("normalize"),
                    1,
                    "idempotent validation node should not accumulate duplicate work",
                )

    def test_invalid_model_evaluation_cannot_reach_decision_or_knowledge(self) -> None:
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            graph = build_phase0_graph(checkpointer)
            state = initial_state(
                "workflow-invalid",
                WorkflowIntent.READ_ONLY,
                include_physical=True,
                include_metrics=True,
            )
            state["model_evaluation"] = evaluation(ResultStatus.INVALID).model_dump(
                mode="json"
            )
            result = graph.invoke(
                state,
                {"configurable": {"thread_id": "workflow-invalid"}},
            )
            self.assertEqual(result["stage"], WorkflowStage.RESULT_INVALID.value)

    def test_reference_free_physical_evaluation_can_complete(self) -> None:
        physical_metrics = MetricContract(
            contract_id="reference-free-physical-metrics",
            physical_model_authority_ref=artifact("model-authority"),
            metrics=(
                MetricRule(
                    name="pde_residual_rms",
                    role=MetricRole.PRIMARY,
                    direction=MetricDirection.MINIMIZE,
                    evidence_basis=MetricEvidenceBasis.PHYSICAL_MODEL,
                ),
            ),
            primary_order=("pde_residual_rms",),
            aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
        )
        model_evaluation = ModelEvaluationReport(
            report_id="reference-free-evaluation",
            status=ResultStatus.VALID,
            physical_model_authority_ref=artifact("model-authority"),
            metric_values={"pde_residual_rms": 0.01},
            metric_bases={
                "pde_residual_rms": MetricEvidenceBasis.PHYSICAL_MODEL,
            },
            domain_provider_ids=("pinn.residual.v1",),
            checks={"physical_authority_confirmed": True},
        )
        state = initial_state(
            "workflow-reference-free",
            WorkflowIntent.READ_ONLY,
            include_physical=True,
            include_metrics=True,
        )
        state["metric_contract"] = physical_metrics.model_dump(mode="json")
        state["model_evaluation"] = model_evaluation.model_dump(mode="json")

        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            result = build_phase0_graph(checkpointer).invoke(
                state,
                {"configurable": {"thread_id": "workflow-reference-free"}},
            )

        self.assertEqual(result["stage"], WorkflowStage.COMPLETED.value)

    def test_smoke_and_full_run_have_separate_approval_gates(self) -> None:
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            graph = build_phase0_graph(checkpointer)
            smoke_config = {"configurable": {"thread_id": "workflow-smoke"}}
            result = graph.invoke(
                initial_state(
                    "workflow-smoke",
                    WorkflowIntent.SMOKE,
                    include_physical=True,
                    include_metrics=True,
                    include_evaluation=True,
                    include_experiment=True,
                ),
                smoke_config,
            )
            self.assertEqual(
                result["stage"], WorkflowStage.NEEDS_EXPERIMENT_APPROVAL.value
            )
            result = graph.invoke(
                Command(
                    resume={
                        "approval": approval(
                            "workflow-smoke", ApprovalKind.EXPERIMENT
                        ).model_dump(mode="json")
                    }
                ),
                smoke_config,
            )
            self.assertEqual(result["stage"], WorkflowStage.SMOKE_APPROVED.value)

            full_config = {"configurable": {"thread_id": "workflow-full"}}
            full_state = initial_state(
                "workflow-full",
                WorkflowIntent.FULL_RUN,
                include_physical=True,
                include_metrics=True,
                include_evaluation=True,
                include_experiment=True,
                smoke_status=ResultStatus.VALID,
            )
            full_state["approvals"].append(
                approval("workflow-full", ApprovalKind.EXPERIMENT).model_dump(
                    mode="json"
                )
            )
            result = graph.invoke(full_state, full_config)
            self.assertEqual(
                result["stage"], WorkflowStage.NEEDS_FULL_RUN_APPROVAL.value
            )
            result = graph.invoke(
                Command(
                    resume={
                        "approval": approval(
                            "workflow-full", ApprovalKind.FULL_RUN
                        ).model_dump(mode="json")
                    }
                ),
                full_config,
            )
            self.assertEqual(result["stage"], WorkflowStage.FULL_APPROVED.value)

    def test_full_run_is_blocked_without_validated_smoke(self) -> None:
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            graph = build_phase0_graph(checkpointer)
            state = initial_state(
                "workflow-no-smoke",
                WorkflowIntent.FULL_RUN,
                include_physical=True,
                include_metrics=True,
                include_evaluation=True,
                include_experiment=True,
            )
            state["approvals"].append(
                approval("workflow-no-smoke", ApprovalKind.EXPERIMENT).model_dump(
                    mode="json"
                )
            )
            result = graph.invoke(
                state,
                {"configurable": {"thread_id": "workflow-no-smoke"}},
            )
            self.assertEqual(
                result["stage"], WorkflowStage.NEEDS_SMOKE_VALIDATION.value
            )

    def test_approval_from_another_workflow_is_rejected(self) -> None:
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            graph = build_phase0_graph(checkpointer)
            config = {"configurable": {"thread_id": "workflow-protected"}}
            graph.invoke(
                initial_state(
                    "workflow-protected",
                    WorkflowIntent.SMOKE,
                    include_physical=True,
                    include_metrics=True,
                    include_evaluation=True,
                    include_experiment=True,
                ),
                config,
            )
            with self.assertRaisesRegex(ValueError, "active workflow"):
                graph.invoke(
                    Command(
                        resume={
                            "approval": approval(
                                "different-workflow", ApprovalKind.EXPERIMENT
                            ).model_dump(mode="json")
                        }
                    ),
                    config,
                )

    def test_preloaded_metric_contract_without_user_approval_still_interrupts(self) -> None:
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            graph = build_phase0_graph(checkpointer)
            state = initial_state(
                "workflow-metric-unconfirmed",
                WorkflowIntent.READ_ONLY,
                include_physical=True,
                include_metrics=True,
            )
            state["approvals"] = []
            result = graph.invoke(
                state,
                {
                    "configurable": {
                        "thread_id": "workflow-metric-unconfirmed"
                    }
                },
            )
            self.assertEqual(
                result["stage"], WorkflowStage.NEEDS_METRIC_PRIORITY.value
            )

    def test_workflow_threads_do_not_share_functional_state(self) -> None:
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            graph = build_phase0_graph(checkpointer)
            for workflow_id in ("isolated-a", "isolated-b"):
                graph.invoke(
                    initial_state(workflow_id, WorkflowIntent.READ_ONLY),
                    {"configurable": {"thread_id": workflow_id}},
                )
            a = graph.get_state({"configurable": {"thread_id": "isolated-a"}})
            b = graph.get_state({"configurable": {"thread_id": "isolated-b"}})
            self.assertEqual(a.values["workflow_id"], "isolated-a")
            self.assertEqual(b.values["workflow_id"], "isolated-b")
            self.assertNotEqual(a.values["request"], b.values["request"])

    def test_specialists_declare_persistence_without_hidden_memory(self) -> None:
        manifest = specialist_persistence()
        scopes = {item.specialist: item.scope for item in manifest}
        self.assertEqual(
            scopes["workflow_coordinator"], PersistenceScope.PER_THREAD
        )
        self.assertTrue(
            all(
                item.scope is PersistenceScope.PER_INVOCATION
                for item in manifest
                if item.specialist != "workflow_coordinator"
            )
        )


if __name__ == "__main__":
    unittest.main()

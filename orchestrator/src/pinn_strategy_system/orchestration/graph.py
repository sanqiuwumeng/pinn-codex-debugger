"""Phase 0 read-only LangGraph with persisted human-interrupt gates."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from pinn_strategy_system.contracts import (
    ApprovalKind,
    ApprovalRecord,
    ExperimentSpec,
    MetricContract,
    ModelEvaluationReport,
    PhysicalAuditReport,
    ResultStatus,
    WorkflowRequest,
    WorkflowStage,
    WorkflowState,
    validate_workflow_state,
)

from .policy import approval_payloads, route_workflow

Node = Callable[[WorkflowState], dict[str, Any]]


def build_phase0_graph(checkpointer: Any):
    """Compile the read-only workflow with an explicitly supplied checkpointer."""

    if checkpointer is None:
        raise ValueError("Phase 0 requires an explicit checkpointer")

    builder = StateGraph(WorkflowState)
    builder.add_node("normalize", _normalize)

    _add_interrupt_path(
        builder,
        route="unit_confirmation",
        stage=WorkflowStage.NEEDS_UNIT_CONFIRMATION,
        reason="Physical parameters require a complete passing audit.",
        collector=_collect_physical_audit,
    )
    _add_interrupt_path(
        builder,
        route="unit_warning",
        stage=WorkflowStage.NEEDS_UNIT_WARNING_APPROVAL,
        reason="A non-blocking physical warning requires explicit user approval.",
        collector=_collect_unit_warning_approval,
    )
    _add_interrupt_path(
        builder,
        route="metric_priority",
        stage=WorkflowStage.NEEDS_METRIC_PRIORITY,
        reason="User metric priorities and guardrails are required before decisions.",
        collector=_collect_metric_contract,
    )
    _add_interrupt_path(
        builder,
        route="diagnostic_evidence",
        stage=WorkflowStage.NEEDS_DIAGNOSTIC_EVIDENCE,
        reason="A valid model evaluation is required before decisions.",
        collector=_collect_model_evaluation,
    )
    _add_interrupt_path(
        builder,
        route="experiment_approval",
        stage=WorkflowStage.NEEDS_EXPERIMENT_APPROVAL,
        reason="Smoke execution requires a scoped experiment approval.",
        collector=_collect_experiment_approval,
    )
    _add_interrupt_path(
        builder,
        route="full_run_approval",
        stage=WorkflowStage.NEEDS_FULL_RUN_APPROVAL,
        reason="A validated smoke does not authorize a full run.",
        collector=_collect_full_run_approval,
    )

    terminal_nodes = {
        "completed": _terminal(
            WorkflowStage.COMPLETED,
            "Physical, metric and model-evaluation gates passed.",
        ),
        "smoke_approved": _terminal(
            WorkflowStage.SMOKE_APPROVED,
            "Smoke is approved; Phase 0 does not launch training.",
        ),
        "needs_smoke_validation": _terminal(
            WorkflowStage.NEEDS_SMOKE_VALIDATION,
            "A full run cannot be considered before a validated smoke.",
        ),
        "full_approved": _terminal(
            WorkflowStage.FULL_APPROVED,
            "Full run is approved; execution remains outside the Phase 0 graph.",
        ),
        "result_invalid": _terminal(
            WorkflowStage.RESULT_INVALID,
            "Model evaluation is invalid and cannot support optimization.",
        ),
        "rejected": _terminal(
            WorkflowStage.REJECTED,
            "A mandatory assurance or approval gate rejected the transition.",
        ),
    }
    for name, node in terminal_nodes.items():
        builder.add_node(name, node)
        builder.add_edge(name, END)

    routes = {
        "unit_confirmation": "prepare_unit_confirmation",
        "unit_warning": "prepare_unit_warning",
        "metric_priority": "prepare_metric_priority",
        "diagnostic_evidence": "prepare_diagnostic_evidence",
        "experiment_approval": "prepare_experiment_approval",
        "full_run_approval": "prepare_full_run_approval",
        **{name: name for name in terminal_nodes},
    }
    builder.add_edge(START, "normalize")
    builder.add_conditional_edges("normalize", route_workflow, routes)
    return builder.compile(checkpointer=checkpointer)


def _add_interrupt_path(
    builder: StateGraph,
    *,
    route: str,
    stage: WorkflowStage,
    reason: str,
    collector: Node,
) -> None:
    prepare_name = f"prepare_{route}"
    collect_name = f"collect_{route}"
    builder.add_node(prepare_name, _prepare(stage, reason))
    builder.add_node(collect_name, collector)
    builder.add_edge(prepare_name, collect_name)
    builder.add_edge(collect_name, "normalize")


def _normalize(state: WorkflowState) -> dict[str, Any]:
    normalized = validate_workflow_state(state)
    completed = _mark_completed(normalized, "normalize")
    return {**normalized, "completed_nodes": completed}


def _prepare(stage: WorkflowStage, reason: str) -> Node:
    def prepare(state: WorkflowState) -> dict[str, Any]:
        return {
            "stage": stage.value,
            "last_transition_reason": reason,
            "completed_nodes": _mark_completed(state, f"prepare:{stage.value}"),
        }

    return prepare


def _interrupt_payload(state: WorkflowState, kind: WorkflowStage) -> dict[str, Any]:
    return {
        "kind": kind.value,
        "workflow_id": state["workflow_id"],
        "reason": state.get("last_transition_reason", ""),
        "schema_version": "1.0",
    }


def _collect_physical_audit(state: WorkflowState) -> dict[str, Any]:
    response = _require_mapping(
        interrupt(_interrupt_payload(state, WorkflowStage.NEEDS_UNIT_CONFIRMATION))
    )
    report = PhysicalAuditReport.model_validate(
        _require_field(response, "physical_audit")
    )
    return {
        "physical_audit": report.model_dump(mode="json"),
        "stage": WorkflowStage.PHYSICAL_AUDIT.value,
        "completed_nodes": _mark_completed(state, "collect:physical_audit"),
    }


def _collect_unit_warning_approval(state: WorkflowState) -> dict[str, Any]:
    response = _require_mapping(
        interrupt(_interrupt_payload(state, WorkflowStage.NEEDS_UNIT_WARNING_APPROVAL))
    )
    approval = ApprovalRecord.model_validate(_require_field(response, "approval"))
    _require_approval_scope(state, approval, ApprovalKind.UNIT_WARNING)
    return {
        "approvals": _append_approval(state, approval),
        "completed_nodes": _mark_completed(state, "collect:unit_warning_approval"),
    }


def _collect_metric_contract(state: WorkflowState) -> dict[str, Any]:
    response = _require_mapping(
        interrupt(_interrupt_payload(state, WorkflowStage.NEEDS_METRIC_PRIORITY))
    )
    contract = MetricContract.model_validate(_require_field(response, "metric_contract"))
    approval = ApprovalRecord.model_validate(_require_field(response, "approval"))
    _require_approval_scope(state, approval, ApprovalKind.METRIC_PRIORITY)
    return {
        "metric_contract": contract.model_dump(mode="json"),
        "approvals": _append_approval(state, approval),
        "completed_nodes": _mark_completed(state, "collect:metric_contract"),
    }


def _collect_model_evaluation(state: WorkflowState) -> dict[str, Any]:
    response = _require_mapping(
        interrupt(_interrupt_payload(state, WorkflowStage.NEEDS_DIAGNOSTIC_EVIDENCE))
    )
    report = ModelEvaluationReport.model_validate(
        _require_field(response, "model_evaluation")
    )
    return {
        "model_evaluation": report.model_dump(mode="json"),
        "completed_nodes": _mark_completed(state, "collect:model_evaluation"),
    }


def _collect_experiment_approval(state: WorkflowState) -> dict[str, Any]:
    response = _require_mapping(
        interrupt(_interrupt_payload(state, WorkflowStage.NEEDS_EXPERIMENT_APPROVAL))
    )
    approval = ApprovalRecord.model_validate(_require_field(response, "approval"))
    _require_approval_scope(state, approval, ApprovalKind.EXPERIMENT)
    update: dict[str, Any] = {
        "approvals": _append_approval(state, approval),
        "completed_nodes": _mark_completed(state, "collect:experiment_approval"),
    }
    if "experiment_spec" in response:
        experiment = ExperimentSpec.model_validate(response["experiment_spec"])
        request = WorkflowRequest.model_validate(state["request"])
        if experiment.project_id != request.project_id:
            raise ValueError("ExperimentSpec project_id must match the workflow request")
        update["experiment_spec"] = experiment.model_dump(mode="json")
    elif state.get("experiment_spec") is None:
        raise ValueError("experiment approval requires an ExperimentSpec")
    return update


def _collect_full_run_approval(state: WorkflowState) -> dict[str, Any]:
    response = _require_mapping(
        interrupt(_interrupt_payload(state, WorkflowStage.NEEDS_FULL_RUN_APPROVAL))
    )
    approval = ApprovalRecord.model_validate(_require_field(response, "approval"))
    _require_approval_scope(state, approval, ApprovalKind.FULL_RUN)
    return {
        "approvals": _append_approval(state, approval),
        "completed_nodes": _mark_completed(state, "collect:full_run_approval"),
    }


def _terminal(stage: WorkflowStage, reason: str) -> Node:
    def terminal(state: WorkflowState) -> dict[str, Any]:
        return {
            "stage": stage.value,
            "last_transition_reason": reason,
            "completed_nodes": _mark_completed(state, f"terminal:{stage.value}"),
        }

    return terminal


def _require_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("interrupt response must be an object")
    return value


def _require_field(payload: dict[str, Any], name: str) -> Any:
    if name not in payload:
        raise ValueError(f"interrupt response requires {name}")
    return payload[name]


def _require_approval_scope(
    state: WorkflowState,
    approval: ApprovalRecord,
    expected: ApprovalKind,
) -> None:
    if approval.kind is not expected:
        raise ValueError(f"expected {expected.value} approval")
    if approval.workflow_id != state["workflow_id"]:
        raise ValueError("approval workflow_id must match the active workflow")


def _append_approval(
    state: WorkflowState,
    approval: ApprovalRecord,
) -> list[dict[str, Any]]:
    approvals = approval_payloads(state)
    approvals.append(approval.model_dump(mode="json"))
    return approvals


def _mark_completed(state: WorkflowState, node: str) -> list[str]:
    completed = list(state.get("completed_nodes", []))
    if node not in completed:
        completed.append(node)
    return completed

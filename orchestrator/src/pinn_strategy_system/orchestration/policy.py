"""Pure routing and persistence policies for the Phase 0 workflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pinn_strategy_system.contracts import (
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    AuditStatus,
    ModelEvaluationReport,
    PhysicalAuditReport,
    ResultStatus,
    WorkflowIntent,
    WorkflowRequest,
    WorkflowState,
)


class PersistenceScope(StrEnum):
    STATELESS = "STATELESS"
    PER_INVOCATION = "PER_INVOCATION"
    PER_THREAD = "PER_THREAD"


@dataclass(frozen=True)
class SpecialistPersistence:
    specialist: str
    scope: PersistenceScope
    rationale: str


def specialist_persistence() -> tuple[SpecialistPersistence, ...]:
    """Return an immutable manifest; no specialist receives hidden memory."""

    return (
        SpecialistPersistence(
            "physical_auditor",
            PersistenceScope.PER_INVOCATION,
            "Consumes an explicit parameter manifest and emits one audit report.",
        ),
        SpecialistPersistence(
            "metric_preference_gate",
            PersistenceScope.PER_INVOCATION,
            "Consumes only the current user-authored MetricContract.",
        ),
        SpecialistPersistence(
            "model_evaluator",
            PersistenceScope.PER_INVOCATION,
            "Reads explicit model authority and evidence refs; arrays stay outside state.",
        ),
        SpecialistPersistence(
            "domain_metric_provider",
            PersistenceScope.PER_INVOCATION,
            "Only case-selected providers receive explicit aligned field context.",
        ),
        SpecialistPersistence(
            "retrieval_provider",
            PersistenceScope.PER_INVOCATION,
            "Every query carries explicit project and evidence scope.",
        ),
        SpecialistPersistence(
            "workflow_coordinator",
            PersistenceScope.PER_THREAD,
            "Only declared WorkflowState is checkpointed by LangGraph.",
        ),
    )


def route_workflow(state: WorkflowState) -> str:
    """Return the next explicit graph route without mutating state."""

    physical_payload = state.get("physical_audit")
    if physical_payload is None:
        return "unit_confirmation"
    physical = PhysicalAuditReport.model_validate(physical_payload)
    if physical.status in {
        AuditStatus.NEEDS_UNIT_CONFIRMATION,
        AuditStatus.NEEDS_EVIDENCE,
    }:
        return "unit_confirmation"
    if physical.status is AuditStatus.REJECT:
        return "rejected"
    if physical.status is AuditStatus.WARN:
        warning = _latest_approval(state, ApprovalKind.UNIT_WARNING)
        if warning is None:
            return "unit_warning"
        if warning.decision is ApprovalDecision.REJECTED:
            return "rejected"

    metric_approval = _latest_approval(state, ApprovalKind.METRIC_PRIORITY)
    if state.get("metric_contract") is None or metric_approval is None:
        return "metric_priority"
    if metric_approval.decision is ApprovalDecision.REJECTED:
        return "rejected"

    evaluation_payload = state.get("model_evaluation")
    if evaluation_payload is None:
        return "diagnostic_evidence"
    evaluation = ModelEvaluationReport.model_validate(evaluation_payload)
    if evaluation.status is ResultStatus.INVALID:
        return "result_invalid"

    request = WorkflowRequest.model_validate(state["request"])
    if request.intent is WorkflowIntent.READ_ONLY:
        return "completed"

    if state.get("experiment_spec") is None:
        return "experiment_evidence"

    experiment_approval = _latest_approval(state, ApprovalKind.EXPERIMENT)
    if experiment_approval is None:
        return "experiment_approval"
    if experiment_approval.decision is ApprovalDecision.REJECTED:
        return "rejected"

    if request.intent is WorkflowIntent.SMOKE:
        return "smoke_approved"

    if state.get("smoke_validation_status") != ResultStatus.VALID.value:
        return "needs_smoke_validation"

    full_approval = _latest_approval(state, ApprovalKind.FULL_RUN)
    if full_approval is None:
        return "full_run_approval"
    if full_approval.decision is ApprovalDecision.REJECTED:
        return "rejected"
    return "full_approved"


def _latest_approval(
    state: WorkflowState,
    kind: ApprovalKind,
) -> ApprovalRecord | None:
    approvals = state.get("approvals", [])
    parsed = [
        ApprovalRecord.model_validate(item)
        for item in approvals
        if item.get("kind") == kind.value
    ]
    return parsed[-1] if parsed else None


def approval_payloads(state: WorkflowState) -> list[dict[str, Any]]:
    """Return a defensive copy of declared approval data."""

    return [dict(item) for item in state.get("approvals", [])]

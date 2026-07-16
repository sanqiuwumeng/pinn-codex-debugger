"""Serializable LangGraph state boundary.

The graph stores JSON projections of versioned contracts. Large artifacts remain
outside this envelope and are represented only by immutable ArtifactRef objects.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict, cast

from pydantic import Field, model_validator

from .enums import ResultStatus, WorkflowStage
from .models import (
    ApprovalRecord,
    ArtifactRef,
    DecisionRecord,
    ExperimentSpec,
    MetricContract,
    ModelEvaluationReport,
    PhysicalAuditReport,
    VersionedModel,
    WorkflowRequest,
)


class WorkflowState(TypedDict, total=False):
    schema_version: str
    workflow_id: str
    request: dict[str, Any]
    stage: str
    physical_audit: dict[str, Any]
    metric_contract: dict[str, Any]
    model_evaluation: dict[str, Any]
    experiment_spec: dict[str, Any]
    decision: dict[str, Any]
    approvals: list[dict[str, Any]]
    artifact_refs: list[dict[str, Any]]
    smoke_validation_status: str
    completed_nodes: list[str]
    last_transition_reason: str


class WorkflowStateEnvelope(VersionedModel):
    workflow_id: str = Field(min_length=1, max_length=256)
    request: WorkflowRequest
    stage: WorkflowStage = WorkflowStage.RECEIVED
    physical_audit: PhysicalAuditReport | None = None
    metric_contract: MetricContract | None = None
    model_evaluation: ModelEvaluationReport | None = None
    experiment_spec: ExperimentSpec | None = None
    decision: DecisionRecord | None = None
    approvals: tuple[ApprovalRecord, ...] = ()
    artifact_refs: tuple[ArtifactRef, ...] = ()
    smoke_validation_status: ResultStatus = ResultStatus.NOT_EVALUATED
    completed_nodes: tuple[str, ...] = ()
    last_transition_reason: str = Field(default="", max_length=4096)

    @model_validator(mode="after")
    def request_and_state_ids_match(self) -> "WorkflowStateEnvelope":
        if self.workflow_id != self.request.workflow_id:
            raise ValueError("workflow_id must match request.workflow_id")
        return self

    def to_state(self) -> WorkflowState:
        payload = self.model_dump(mode="json", exclude_none=True)
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > 1_048_576:
            raise ValueError("WorkflowState exceeds the 1 MiB small-state boundary")
        return cast(WorkflowState, payload)


def validate_workflow_state(state: WorkflowState | dict[str, Any]) -> WorkflowState:
    """Validate a state mapping and return its normalized JSON projection."""

    envelope = WorkflowStateEnvelope.model_validate(state)
    return envelope.to_state()

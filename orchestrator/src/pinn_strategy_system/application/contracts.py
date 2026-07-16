"""Explicit operator inputs and stable application-service results."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import Field, JsonValue, model_validator

from pinn_strategy_system.contracts import (
    ApprovalRecord,
    ChunkingPolicy,
    DerivativeScalingSpec,
    EquationAuditSpec,
    ExperimentDraft,
    MetricContract,
    ModelEvaluationReport,
    PhysicalModelAuthority,
    PhysicalParameterInput,
    ReferenceEvidence,
    ResultStatus,
    RunManifest,
    UnitSystemContract,
    VersionedModel,
    WorkflowRequest,
)
from pinn_strategy_system.retrieval import RetrievalScope


class OperationOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    NEEDS_INPUT = "NEEDS_INPUT"
    GATE_REJECTED = "GATE_REJECTED"
    RUN_FAILED = "RUN_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ApplicationResult(VersionedModel):
    command: str = Field(min_length=1, max_length=128)
    outcome: OperationOutcome
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    message: str = Field(min_length=1, max_length=4096)
    workflow_id: str | None = Field(default=None, max_length=256)
    stage: str | None = Field(default=None, max_length=256)
    data: dict[str, JsonValue] = Field(default_factory=dict)


class OperatorCase(VersionedModel):
    case_id: str = Field(min_length=1, max_length=256)
    request: WorkflowRequest
    unit_system: UnitSystemContract
    physical_model: PhysicalModelAuthority
    parameters: tuple[PhysicalParameterInput, ...] = ()
    equations: tuple[EquationAuditSpec, ...] = ()
    derivative_scaling: tuple[DerivativeScalingSpec, ...] = ()
    references: tuple[ReferenceEvidence, ...] = ()
    metric_contract: MetricContract | None = None
    model_evaluation: ModelEvaluationReport | None = None
    experiment_draft: ExperimentDraft | None = None
    approvals: tuple[ApprovalRecord, ...] = ()
    smoke_validation_status: ResultStatus = ResultStatus.NOT_EVALUATED
    smoke_manifest: RunManifest | None = None
    full_manifest: RunManifest | None = None
    execution_profile_path: Path | None = None
    chunking_policy: ChunkingPolicy | None = None
    retrieval_scope: RetrievalScope | None = None

    @model_validator(mode="after")
    def identifiers_and_boundaries_match(self) -> Self:
        if self.physical_model.project_id != self.request.project_id:
            raise ValueError("physical model project_id must match workflow request")
        if self.physical_model.unit_system != self.unit_system:
            raise ValueError("physical model must use the declared unit system")
        if any(
            approval.workflow_id != self.request.workflow_id
            for approval in self.approvals
        ):
            raise ValueError("every approval must match the workflow_id")
        for manifest in (self.smoke_manifest, self.full_manifest):
            if manifest is not None and manifest.workflow_id != self.request.workflow_id:
                raise ValueError("run manifest workflow_id must match the case")
        if (
            self.execution_profile_path is not None
            and not self.execution_profile_path.is_absolute()
        ):
            raise ValueError("execution_profile_path must be absolute")
        if (
            self.retrieval_scope is not None
            and self.retrieval_scope.project_id != self.request.project_id
        ):
            raise ValueError("retrieval scope project_id must match the case")
        return self

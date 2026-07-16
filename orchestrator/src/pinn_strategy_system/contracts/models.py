"""Frozen Pydantic contracts for cross-layer data exchange."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from .enums import (
    AggregationPolicy,
    ApprovalDecision,
    ApprovalKind,
    ArtifactCollectionStatus,
    AuditStatus,
    BackendRunPhase,
    ClaimScope,
    DecisionStatus,
    EvidenceLevel,
    KnowledgeKind,
    KnowledgeValidity,
    MetricDirection,
    MetricEvidenceBasis,
    MetricRole,
    MonitorOutcome,
    ParameterConsumption,
    ReferenceKind,
    ResultStatus,
    RunEventType,
    RunSubmissionStatus,
    WorkflowIntent,
)

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ShortText = Annotated[str, Field(min_length=1, max_length=4096)]
Identifier = Annotated[str, Field(min_length=1, max_length=256)]


class VersionedModel(BaseModel):
    """Base for strict, immutable and JSON-serializable interchange models."""

    schema_version: Literal["1.0"] = "1.0"
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=False,
        validate_default=True,
    )


class ArtifactRef(VersionedModel):
    artifact_id: Identifier
    uri: ShortText
    sha256: Sha256
    media_type: str | None = Field(default=None, max_length=256)
    size_bytes: int | None = Field(default=None, ge=0)


class SourceRef(VersionedModel):
    uri: ShortText
    sha256: Sha256 | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    symbol: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def line_range_is_ordered(self) -> Self:
        if self.line_end is not None and self.line_start is None:
            raise ValueError("line_end requires line_start")
        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            raise ValueError("line_end must be greater than or equal to line_start")
        return self


class SourceSnapshot(VersionedModel):
    snapshot_id: Identifier
    project_id: Identifier
    root_uri: ShortText
    created_at: datetime
    file_manifest_ref: ArtifactRef
    environment_ref: ArtifactRef
    repo_commit: str | None = Field(default=None, max_length=128)
    dataset_refs: tuple[ArtifactRef, ...] = ()


class WorkflowRequest(VersionedModel):
    request_id: Identifier
    workflow_id: Identifier
    project_id: Identifier
    objective: ShortText
    intent: WorkflowIntent = WorkflowIntent.READ_ONLY
    snapshot_ref: ArtifactRef
    requested_by: Identifier


class RetrievalRequest(VersionedModel):
    request_id: Identifier
    project_id: Identifier
    query: ShortText
    evidence: tuple[str, ...] = ()
    anchors: tuple[str, ...] = ()
    max_sections: int = Field(default=5, ge=1, le=10)


class EvidenceItem(VersionedModel):
    source_uri: ShortText
    source_sha256: Sha256
    heading: ShortText
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    excerpt: ShortText
    score: FiniteFloat
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def evidence_range_is_ordered(self) -> Self:
        if self.line_end < self.line_start:
            raise ValueError("evidence line_end must not precede line_start")
        return self


class RetrievalResponse(VersionedModel):
    request_id: Identifier
    provider: Identifier
    backend: Identifier
    source_sha256: Sha256
    evidence: tuple[EvidenceItem, ...] = ()
    read_only: bool = True

    @model_validator(mode="after")
    def provider_is_always_read_only(self) -> Self:
        if not self.read_only:
            raise ValueError("retrieval providers must be read-only")
        return self


class ChunkingPolicy(VersionedModel):
    policy_id: Identifier
    max_characters: int = Field(ge=128, le=100_000)
    overlap_characters: int = Field(ge=0)
    preserve_headings: bool = True
    preserve_code_blocks: bool = True
    document_types: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def overlap_is_smaller_than_chunk(self) -> Self:
        if self.overlap_characters >= self.max_characters:
            raise ValueError("chunk overlap must be smaller than max_characters")
        return self


class ChunkMetadata(VersionedModel):
    project_id: Identifier
    source_ref: SourceRef
    artifact_range: str | None = Field(default=None, max_length=1024)
    repo_commit: str | None = Field(default=None, max_length=128)
    experiment_id: str | None = Field(default=None, max_length=256)
    run_id: str | None = Field(default=None, max_length=256)
    dataset_hash: Sha256 | None = None
    environment_hash: Sha256 | None = None
    model_family: str | None = Field(default=None, max_length=256)
    pde_family: str | None = Field(default=None, max_length=256)
    task_type: str | None = Field(default=None, max_length=256)
    domain_provider_id: str | None = Field(default=None, max_length=256)
    output_channels: tuple[str, ...] = ()
    dimensional_signatures: tuple[str, ...] = ()
    failure_signatures: tuple[str, ...] = ()
    framework: str | None = Field(default=None, max_length=256)
    document_type: Literal[
        "HANDBOOK",
        "CODE_MAP",
        "EXPERIMENT_REPORT",
        "WIKI",
        "SKILL",
        "FAILURE_REPORT",
    ]
    validation_status: Literal[
        "SOURCE_VERIFIED",
        "RESULT_VALIDATED",
        "APPROVED",
    ]
    valid_from: datetime
    supersedes: tuple[str, ...] = ()
    language: str = Field(min_length=2, max_length=32)

    @model_validator(mode="after")
    def chunk_has_rebuildable_source_range(self) -> Self:
        if self.source_ref.sha256 is None:
            raise ValueError("chunk source_ref requires sha256")
        if self.source_ref.line_start is None and not self.artifact_range:
            raise ValueError("chunk requires a line range or artifact_range")
        return self


class KnowledgeChunk(VersionedModel):
    chunk_id: Identifier
    text: ShortText
    chunk_sha256: Sha256
    metadata: ChunkMetadata


class ConversionStep(VersionedModel):
    operation: ShortText
    factor: FiniteFloat = 1.0
    offset: FiniteFloat = 0.0
    apply_site: ShortText
    source_ref: SourceRef


class UnitSystemContract(VersionedModel):
    unit_system_id: Identifier
    name: ShortText
    quantity_units: dict[str, str] = Field(min_length=1)
    source_refs: tuple[SourceRef, ...] = ()
    confirmed_by_user: bool

    @model_validator(mode="after")
    def quantity_unit_entries_are_explicit(self) -> Self:
        if any(
            not quantity.strip() or not unit.strip()
            for quantity, unit in self.quantity_units.items()
        ):
            raise ValueError("quantity_units requires non-empty quantity and unit text")
        return self


class PhysicalModelAuthority(VersionedModel):
    authority_id: Identifier
    project_id: Identifier
    model_family: Identifier
    pde_family: Identifier
    task_type: Identifier
    governing_equation_refs: tuple[SourceRef, ...] = Field(min_length=1)
    boundary_condition_refs: tuple[SourceRef, ...] = ()
    initial_condition_refs: tuple[SourceRef, ...] = ()
    geometry_refs: tuple[SourceRef, ...] = ()
    parameter_source_refs: tuple[SourceRef, ...] = ()
    output_channels: tuple[str, ...] = Field(min_length=1)
    unit_system: UnitSystemContract
    confirmed_by_user: bool


class ReferenceEvidence(VersionedModel):
    reference_id: Identifier
    authority_id: Identifier
    kind: ReferenceKind
    artifact_ref: ArtifactRef
    output_channels: tuple[str, ...] = Field(min_length=1)
    coordinate_system: ShortText
    channel_units: dict[str, str] = Field(min_length=1)
    source_refs: tuple[SourceRef, ...] = ()
    test_case_only: bool = False
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def every_output_channel_has_a_unit(self) -> Self:
        if set(self.output_channels) != set(self.channel_units):
            raise ValueError("channel_units must cover every output channel exactly")
        return self


class PhysicalParameterInput(VersionedModel):
    parameter_id: Identifier
    symbol: Identifier
    meaning: ShortText
    quantity_kind: Identifier
    raw_value: FiniteFloat
    raw_unit: str | None = Field(default=None, max_length=256)
    source_ref: SourceRef
    load_sites: tuple[SourceRef, ...] = ()
    use_sites: tuple[SourceRef, ...] = ()
    conversion_steps: tuple[ConversionStep, ...] = ()
    consumption: ParameterConsumption = ParameterConsumption.DERIVED_MANIFEST
    semantic_tags: tuple[str, ...] = ()
    plausible_min: FiniteFloat | None = None
    plausible_max: FiniteFloat | None = None

    @model_validator(mode="after")
    def plausible_range_is_ordered(self) -> Self:
        if (
            self.plausible_min is not None
            and self.plausible_max is not None
            and self.plausible_max < self.plausible_min
        ):
            raise ValueError("plausible_max must be greater than or equal to plausible_min")
        return self


class PhysicalParameterRecord(VersionedModel):
    parameter_id: Identifier
    symbol: Identifier
    meaning: ShortText
    quantity_kind: Identifier
    unit_system_id: Identifier
    raw_value: FiniteFloat
    raw_unit: ShortText
    canonical_value: FiniteFloat
    canonical_unit: ShortText
    dimensional_signature: ShortText
    conversion_factor: FiniteFloat
    conversion_offset: FiniteFloat = 0.0
    source_ref: SourceRef
    load_sites: tuple[SourceRef, ...] = ()
    use_sites: tuple[SourceRef, ...] = ()
    conversion_steps: tuple[ConversionStep, ...] = ()
    confirmation_status: AuditStatus


class EquationTermSpec(VersionedModel):
    term_id: Identifier
    unit: ShortText
    source_ref: SourceRef
    semantic_tags: tuple[str, ...] = ()


class EquationAuditSpec(VersionedModel):
    equation_id: Identifier
    equation_kind: Literal["PDE", "BC", "IC", "CONSTITUTIVE"]
    additive_terms: tuple[EquationTermSpec, ...] = Field(min_length=2)


class DerivativeScalingSpec(VersionedModel):
    check_id: Identifier
    coordinate: Identifier
    derivative_order: int = Field(ge=1, le=4)
    coordinate_scale: FiniteFloat
    output_scale: FiniteFloat = 1.0
    observed_factor: FiniteFloat
    source_ref: SourceRef

    @model_validator(mode="after")
    def coordinate_scale_is_nonzero(self) -> Self:
        if self.coordinate_scale == 0:
            raise ValueError("coordinate_scale must be nonzero")
        return self


class AuditFinding(VersionedModel):
    code: Identifier
    status: AuditStatus
    message: ShortText
    parameter_ids: tuple[str, ...] = ()
    source_refs: tuple[SourceRef, ...] = ()
    expected: str | None = Field(default=None, max_length=1024)
    observed: str | None = Field(default=None, max_length=1024)


class PhysicalAuditReport(VersionedModel):
    report_id: Identifier
    unit_system_id: Identifier
    status: AuditStatus
    parameter_records: tuple[PhysicalParameterRecord, ...] = ()
    findings: tuple[AuditFinding, ...] = ()
    derived_manifest_ref: ArtifactRef | None = None
    source_files_unchanged: bool = True

    @model_validator(mode="after")
    def source_overwrite_is_never_accepted(self) -> Self:
        if not self.source_files_unchanged:
            raise ValueError("physical audit must not overwrite source files")
        if self.status is AuditStatus.PASS and any(
            finding.status in {AuditStatus.REJECT, AuditStatus.NEEDS_UNIT_CONFIRMATION}
            for finding in self.findings
        ):
            raise ValueError("PASS report cannot contain blocking findings")
        return self


class TimeWindow(VersionedModel):
    start: FiniteFloat
    end: FiniteFloat
    unit: ShortText

    @model_validator(mode="after")
    def end_is_not_before_start(self) -> Self:
        if self.end < self.start:
            raise ValueError("time-window end must be greater than or equal to start")
        return self


class MetricRule(VersionedModel):
    name: Identifier
    role: MetricRole
    direction: MetricDirection
    evidence_basis: MetricEvidenceBasis
    required: bool = True
    threshold: FiniteFloat | None = None
    max_regression: FiniteFloat | None = Field(default=None, ge=0)
    max_relative_regression: FiniteFloat | None = Field(default=None, ge=0)
    weight: FiniteFloat | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def role_has_required_policy_fields(self) -> Self:
        if self.role is MetricRole.HARD_CONSTRAINT and self.threshold is None:
            raise ValueError("hard constraints require an absolute threshold")
        if (
            self.role is MetricRole.GUARDRAIL
            and self.threshold is None
            and self.max_regression is None
            and self.max_relative_regression is None
        ):
            raise ValueError(
                "guardrails require an absolute threshold, absolute regression "
                "or relative regression limit"
            )
        if self.max_regression is not None and self.unit is None:
            raise ValueError("absolute metric regression requires an explicit unit")
        return self


class MetricContract(VersionedModel):
    contract_id: Identifier
    physical_model_authority_ref: ArtifactRef
    reference_evidence_refs: tuple[ArtifactRef, ...] = ()
    metrics: tuple[MetricRule, ...] = Field(min_length=1)
    primary_order: tuple[str, ...] = Field(min_length=1)
    aggregation_policy: AggregationPolicy
    scalar_aggregation_authorized: bool = False
    roi_labels: tuple[str, ...] = ()
    time_windows: tuple[TimeWindow, ...] = ()
    acceptable_regression_notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def metric_policy_is_complete(self) -> Self:
        names = [rule.name for rule in self.metrics]
        if len(set(names)) != len(names):
            raise ValueError("metric names must be unique")
        primary = {
            rule.name for rule in self.metrics if rule.role is MetricRole.PRIMARY
        }
        if not primary:
            raise ValueError("at least one primary metric is required")
        if set(self.primary_order) != primary or len(self.primary_order) != len(primary):
            raise ValueError("primary_order must list every primary metric exactly once")
        if (
            any(
                rule.evidence_basis is MetricEvidenceBasis.REFERENCE_EVIDENCE
                for rule in self.metrics
            )
            and not self.reference_evidence_refs
        ):
            raise ValueError(
                "reference-backed metrics require at least one reference evidence"
            )
        if self.aggregation_policy is AggregationPolicy.SCALAR:
            if not self.scalar_aggregation_authorized:
                raise ValueError("scalar aggregation requires explicit user authorization")
            weights = {
                rule.name: rule.weight
                for rule in self.metrics
                if rule.role is MetricRole.PRIMARY
            }
            if any(value is None for value in weights.values()):
                raise ValueError("every primary metric requires a scalar weight")
            if sum(value or 0.0 for value in weights.values()) <= 0:
                raise ValueError("scalar weights must have positive total")
        return self


class MetricValueSet(VersionedModel):
    subject_id: Identifier
    values: dict[str, FiniteFloat]


class LocalizedError(VersionedModel):
    flat_index: int = Field(ge=0)
    coordinates: dict[str, str | int | FiniteFloat]
    prediction: FiniteFloat
    reference: FiniteFloat
    signed_error: FiniteFloat
    absolute_error: FiniteFloat = Field(ge=0)
    context: dict[str, str | int | FiniteFloat | bool | None] = Field(
        default_factory=dict
    )


class ConnectedRegionSummary(VersionedModel):
    region_id: Identifier
    time_value: str | int | FiniteFloat | None = None
    channel_value: str | int | FiniteFloat | None = None
    point_count: int = Field(ge=1)
    peak_absolute_error: FiniteFloat = Field(ge=0)
    centroid: dict[str, FiniteFloat]
    bounds: dict[str, tuple[FiniteFloat, FiniteFloat]]


class TimeSliceMetric(VersionedModel):
    time_value: str | int | FiniteFloat
    metrics: dict[str, FiniteFloat]
    max_location: dict[str, str | int | FiniteFloat]


class PredictionAnalysisReport(VersionedModel):
    report_id: Identifier
    status: ResultStatus
    prediction_ref: ArtifactRef
    reference_ref: ArtifactRef
    global_metrics: dict[str, FiniteFloat] = Field(default_factory=dict)
    percentile_errors: dict[str, FiniteFloat] = Field(default_factory=dict)
    max_abs: LocalizedError | None = None
    top_k: tuple[LocalizedError, ...] = ()
    connected_regions: tuple[ConnectedRegionSummary, ...] = ()
    time_slices: tuple[TimeSliceMetric, ...] = ()
    roi_metrics: dict[str, dict[str, FiniteFloat]] = Field(default_factory=dict)
    domain_metrics: dict[str, FiniteFloat] = Field(default_factory=dict)
    alignment_checks: dict[str, bool] = Field(default_factory=dict)
    findings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_report_contains_localization(self) -> Self:
        if self.status is ResultStatus.VALID:
            if self.max_abs is None:
                raise ValueError("valid prediction report requires max_abs localization")
            if not self.alignment_checks or not all(self.alignment_checks.values()):
                raise ValueError("valid prediction report requires passing alignment checks")
        return self


class ModelEvaluationReport(VersionedModel):
    report_id: Identifier
    status: ResultStatus
    physical_model_authority_ref: ArtifactRef
    metric_values: dict[str, FiniteFloat] = Field(default_factory=dict)
    metric_bases: dict[str, MetricEvidenceBasis] = Field(default_factory=dict)
    prediction_analysis_ref: ArtifactRef | None = None
    diagnostic_refs: tuple[ArtifactRef, ...] = ()
    domain_provider_ids: tuple[str, ...] = ()
    checks: dict[str, bool] = Field(default_factory=dict)
    findings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_evaluation_has_traceable_metrics(self) -> Self:
        if set(self.metric_values) != set(self.metric_bases):
            raise ValueError("metric_bases must identify every metric value exactly")
        if self.status is ResultStatus.VALID:
            if not self.metric_values:
                raise ValueError("valid model evaluation requires metric values")
            if not self.checks or not all(self.checks.values()):
                raise ValueError("valid model evaluation requires passing checks")
        return self


class PredictionComparisonReport(VersionedModel):
    report_id: Identifier
    status: ResultStatus
    baseline_report: PredictionAnalysisReport
    candidate_report: PredictionAnalysisReport
    metric_deltas: dict[str, FiniteFloat] = Field(default_factory=dict)
    error_migrated: bool = False
    findings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_comparison_requires_two_valid_reports(self) -> Self:
        if self.status is ResultStatus.VALID and (
            self.baseline_report.status is not ResultStatus.VALID
            or self.candidate_report.status is not ResultStatus.VALID
        ):
            raise ValueError("valid comparison requires valid baseline and candidate")
        return self


class BudgetSpec(VersionedModel):
    max_steps: int | None = Field(default=None, ge=1)
    max_seconds: FiniteFloat | None = Field(default=None, gt=0)
    max_cost: FiniteFloat | None = Field(default=None, ge=0)
    resource_description: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def at_least_one_budget_limit(self) -> Self:
        if (
            self.max_steps is None
            and self.max_seconds is None
            and self.max_cost is None
            and self.resource_description is None
        ):
            raise ValueError("budget must declare at least one limit or resource")
        return self


class InterventionChange(VersionedModel):
    target: ShortText
    before: JsonValue
    after: JsonValue
    rationale: ShortText
    source_ref: SourceRef | None = None

    @model_validator(mode="after")
    def intervention_changes_a_value(self) -> Self:
        if self.before == self.after:
            raise ValueError("intervention before and after values must differ")
        return self


class ExperimentDraft(VersionedModel):
    experiment_id: Identifier
    project_id: Identifier
    observed_failure_mechanism: str | None = Field(default=None, max_length=4096)
    supporting_evidence_refs: tuple[ArtifactRef, ...] = ()
    interventions: tuple[InterventionChange, ...] = ()
    unchanged_controls: tuple[str, ...] = ()
    expected_primary_metric_movement: dict[str, ShortText] = Field(
        default_factory=dict
    )
    guardrail_limits: dict[str, FiniteFloat] = Field(default_factory=dict)
    smoke_budget: BudgetSpec | None = None
    full_budget: BudgetSpec | None = None
    falsification_condition: str | None = Field(default=None, max_length=4096)
    rollback_plan: str | None = Field(default=None, max_length=4096)
    source_snapshot_ref: ArtifactRef | None = None
    dataset_refs: tuple[ArtifactRef, ...] = ()
    environment_ref: ArtifactRef | None = None
    random_seed: int | None = Field(default=None, ge=0)
    baseline_run_ref: ArtifactRef | None = None
    metric_contract_ref: ArtifactRef | None = None
    output_root: str | None = Field(default=None, max_length=4096)
    checkpoint_policy: str | None = Field(default=None, max_length=4096)
    expected_artifacts: tuple[str, ...] = ()


class ExperimentSpec(VersionedModel):
    experiment_id: Identifier
    project_id: Identifier
    observed_failure_mechanism: ShortText
    supporting_evidence_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    single_intervention: InterventionChange
    unchanged_controls: tuple[str, ...] = Field(min_length=1)
    expected_primary_metric_movement: dict[str, ShortText]
    guardrail_limits: dict[str, FiniteFloat]
    smoke_budget: BudgetSpec
    full_budget: BudgetSpec
    falsification_condition: ShortText
    rollback_plan: ShortText
    source_snapshot_ref: ArtifactRef
    dataset_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    environment_ref: ArtifactRef
    random_seed: int = Field(ge=0)
    baseline_run_ref: ArtifactRef
    metric_contract_ref: ArtifactRef
    output_root: ShortText
    checkpoint_policy: ShortText
    expected_artifacts: tuple[str, ...] = Field(min_length=1)


class ExperimentCompletenessReport(VersionedModel):
    report_id: Identifier
    status: AuditStatus
    checks: dict[str, bool]
    missing_fields: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    experiment_spec: ExperimentSpec | None = None

    @model_validator(mode="after")
    def passing_report_materializes_a_complete_spec(self) -> Self:
        if self.status is AuditStatus.PASS:
            if self.experiment_spec is None or not all(self.checks.values()):
                raise ValueError("PASS completeness report requires a complete spec")
        return self


class ApprovalRecord(VersionedModel):
    approval_id: Identifier
    workflow_id: Identifier
    kind: ApprovalKind
    decision: ApprovalDecision
    approved_by: Identifier
    approved_at: datetime
    scope: ShortText
    evidence_refs: tuple[ArtifactRef, ...] = ()


class RunManifest(VersionedModel):
    run_id: Identifier
    workflow_id: Identifier
    experiment_id: Identifier
    idempotency_key: Identifier
    environment_name: Identifier
    interpreter: ShortText
    working_directory: ShortText
    command: tuple[str, ...] = Field(min_length=1)
    config_ref: ArtifactRef
    output_root: ShortText
    expected_artifacts: tuple[str, ...] = Field(min_length=1)
    checkpoint_policy: ShortText
    rollback_plan: ShortText


class ExecutionRequest(VersionedModel):
    request_id: Identifier
    manifest: RunManifest
    approval: ApprovalRecord


class BackendRunRef(VersionedModel):
    backend_id: Identifier
    run_id: Identifier
    idempotency_key: Identifier
    reference: ShortText


class PreparedRun(VersionedModel):
    request: ExecutionRequest
    backend_ref: BackendRunRef
    staging_root: ShortText
    prepared_at: datetime
    launch_metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def backend_reference_matches_manifest(self) -> Self:
        manifest = self.request.manifest
        if self.backend_ref.run_id != manifest.run_id:
            raise ValueError("prepared backend reference run_id must match manifest")
        if self.backend_ref.idempotency_key != manifest.idempotency_key:
            raise ValueError(
                "prepared backend reference idempotency_key must match manifest"
            )
        return self


class LogCursor(VersionedModel):
    stdout_offset: int = Field(default=0, ge=0)
    stderr_offset: int = Field(default=0, ge=0)
    observed_at: datetime


class BackendRunStatus(VersionedModel):
    backend_ref: BackendRunRef
    phase: BackendRunPhase
    observed_at: datetime
    process_id: int | None = Field(default=None, ge=1)
    process_create_time: FiniteFloat | None = None
    exit_code: int | None = None
    heartbeat_at: datetime | None = None
    log_cursor: LogCursor | None = None
    produced_artifacts: tuple[str, ...] = ()
    checks: dict[str, bool] = Field(default_factory=dict)
    detail: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def completed_phase_has_success_evidence(self) -> Self:
        if self.phase is BackendRunPhase.COMPLETED:
            if self.exit_code != 0:
                raise ValueError("completed backend status requires exit_code 0")
            if not self.checks or not all(self.checks.values()):
                raise ValueError("completed backend status requires passing checks")
        return self


class RunCancellationRequest(VersionedModel):
    run_id: Identifier
    workflow_id: Identifier
    requested_at: datetime
    reason: ShortText
    approval: ApprovalRecord

    @model_validator(mode="after")
    def cancellation_has_scoped_human_approval(self) -> Self:
        if self.approval.kind is not ApprovalKind.RUN_CANCELLATION:
            raise ValueError("run cancellation requires RUN_CANCELLATION approval")
        if self.approval.decision is not ApprovalDecision.APPROVED:
            raise ValueError("run cancellation requires an approved decision")
        if self.approval.workflow_id != self.workflow_id:
            raise ValueError("cancellation approval workflow_id must match request")
        if self.approval.scope != f"run:{self.run_id}:cancel":
            raise ValueError("cancellation approval scope must match run_id")
        return self


class ArtifactCollectionSpec(VersionedModel):
    run_id: Identifier
    backend_ref: BackendRunRef
    destination_root: ShortText
    required_artifacts: tuple[str, ...] = Field(min_length=1)
    overwrite_existing: Literal[False] = False

    @model_validator(mode="after")
    def collection_reference_matches_run(self) -> Self:
        if self.backend_ref.run_id != self.run_id:
            raise ValueError("collection backend reference run_id must match spec")
        return self


class ArtifactCollectionReport(VersionedModel):
    run_id: Identifier
    status: ArtifactCollectionStatus
    artifact_refs: tuple[ArtifactRef, ...] = ()
    source_manifest_ref: ArtifactRef | None = None
    destination_manifest_ref: ArtifactRef | None = None
    findings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def complete_collection_has_two_manifests(self) -> Self:
        if self.status is ArtifactCollectionStatus.COMPLETE:
            if not self.artifact_refs:
                raise ValueError("complete collection requires collected artifacts")
            manifests = (
                self.source_manifest_ref,
                self.destination_manifest_ref,
            )
            if any(manifest is None for manifest in manifests):
                raise ValueError(
                    "complete collection requires source and destination manifests"
                )
        return self


class RunSubmission(VersionedModel):
    run_id: Identifier
    idempotency_key: Identifier
    status: RunSubmissionStatus
    prepared_run: PreparedRun | None = None
    backend_ref: BackendRunRef | None = None
    last_backend_status: BackendRunStatus | None = None
    collection_report: ArtifactCollectionReport | None = None
    duplicate: bool = False

    @model_validator(mode="after")
    def lifecycle_state_has_required_references(self) -> Self:
        prepared_states = (
            RunSubmissionStatus.PREPARED,
            RunSubmissionStatus.RUNNING,
            RunSubmissionStatus.RUNNING_UNKNOWN,
            RunSubmissionStatus.CANCELLING,
            RunSubmissionStatus.CANCELLED,
            RunSubmissionStatus.COLLECTING,
            RunSubmissionStatus.COMPLETED,
        )
        backend_states = tuple(
            status
            for status in prepared_states
            if status is not RunSubmissionStatus.PREPARED
        )
        if self.status in prepared_states and self.prepared_run is None:
            raise ValueError("prepared lifecycle state requires PreparedRun")
        if self.status in backend_states and self.backend_ref is None:
            raise ValueError("backend lifecycle state requires BackendRunRef")
        terminal_phases = {
            RunSubmissionStatus.CANCELLED: BackendRunPhase.CANCELLED,
            RunSubmissionStatus.COMPLETED: BackendRunPhase.COMPLETED,
        }
        expected_phase = terminal_phases.get(self.status)
        if expected_phase is not None:
            if (
                self.last_backend_status is None
                or self.last_backend_status.phase is not expected_phase
            ):
                raise ValueError(
                    "terminal submission requires matching backend status evidence"
                )
        return self


class RunEvent(VersionedModel):
    event_id: Identifier
    run_id: Identifier
    event_type: RunEventType
    occurred_at: datetime
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    artifact_refs: tuple[ArtifactRef, ...] = ()


class MonitoringPolicy(VersionedModel):
    policy_id: Identifier
    log_stall_seconds: FiniteFloat = Field(gt=0)
    required_artifact_ids: tuple[str, ...] = ()
    metric_upper_bounds: dict[str, FiniteFloat] = Field(default_factory=dict)
    anomaly_event_types: tuple[RunEventType, ...] = (
        RunEventType.LOSS_SPIKE,
        RunEventType.NAN_DETECTED,
        RunEventType.GPU_OOM,
        RunEventType.LOG_STALLED,
        RunEventType.ARTIFACT_MISSING,
    )
    milestone_event_types: tuple[RunEventType, ...] = (
        RunEventType.CHECKPOINT_WRITTEN,
        RunEventType.EARLY_STOP_TRIGGERED,
    )


class MonitoringReport(VersionedModel):
    report_id: Identifier
    run_id: Identifier
    outcome: MonitorOutcome
    trigger_agent: bool
    reasons: tuple[str, ...] = ()
    last_event_at: datetime | None = None
    observed_artifact_ids: tuple[str, ...] = ()


class ValidationReport(VersionedModel):
    report_id: Identifier
    subject_id: Identifier
    status: ResultStatus
    checks: dict[str, bool]
    findings: tuple[str, ...] = ()
    evidence_refs: tuple[ArtifactRef, ...] = ()


class RunValidationInput(VersionedModel):
    run_id: Identifier
    process_exit_code: int
    physical_audit: PhysicalAuditReport
    model_evaluation: ModelEvaluationReport
    metric_decision: DecisionRecord
    required_artifacts: tuple[str, ...] = Field(min_length=1)
    produced_artifacts: dict[str, ArtifactRef] = Field(default_factory=dict)
    run_manifest_ref: ArtifactRef
    source_snapshot_ref: ArtifactRef
    dataset_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    environment_ref: ArtifactRef
    random_seed: int = Field(ge=0)


class DecisionRecord(VersionedModel):
    decision_id: Identifier
    status: DecisionStatus
    observed_failure_mechanism: ShortText
    selected_intervention: str | None = Field(default=None, max_length=4096)
    unchanged_controls: tuple[str, ...] = ()
    supporting_evidence_refs: tuple[ArtifactRef, ...] = ()
    expected_primary_metric_movement: dict[str, str] = Field(default_factory=dict)
    guardrail_limits: dict[str, FiniteFloat] = Field(default_factory=dict)
    falsification_condition: str | None = Field(default=None, max_length=4096)
    rollback_plan: str | None = Field(default=None, max_length=4096)
    reasons: tuple[str, ...] = ()


class KnowledgeCandidate(VersionedModel):
    candidate_id: Identifier
    kind: KnowledgeKind
    title: ShortText
    statement: ShortText
    evidence_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    run_ids: tuple[str, ...] = ()
    validation_status: ResultStatus
    supersedes: tuple[str, ...] = ()
    pattern_key: str | None = Field(default=None, max_length=512)
    repeated_validated_pattern_count: int = Field(default=1, ge=1)
    human_approval_required: bool = True

    @model_validator(mode="after")
    def skill_candidate_requires_repetition(self) -> Self:
        if self.kind is KnowledgeKind.SKILL and self.repeated_validated_pattern_count < 2:
            raise ValueError("SkillCandidate requires repeated validated patterns")
        if self.kind is KnowledgeKind.SKILL and not self.pattern_key:
            raise ValueError("SkillCandidate requires a stable pattern_key")
        if not self.human_approval_required:
            raise ValueError("knowledge promotion always requires human approval")
        return self


class WikiEntryCandidate(VersionedModel):
    candidate_id: Identifier
    version: int = Field(ge=1)
    title: ShortText
    conclusion: ShortText
    run_id: Identifier
    source_snapshot_ref: ArtifactRef
    dataset_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    environment_ref: ArtifactRef
    metric_report_ref: ArtifactRef
    physical_audit_ref: ArtifactRef
    reproducibility_report_ref: ArtifactRef
    validation_report_ref: ArtifactRef
    evidence_level: EvidenceLevel
    claim_scope: ClaimScope
    validity_status: KnowledgeValidity = KnowledgeValidity.CANDIDATE
    supersedes: tuple[str, ...] = ()
    human_approval_required: bool = True

    @model_validator(mode="after")
    def smoke_does_not_claim_scientific_effectiveness(self) -> Self:
        if (
            self.evidence_level is EvidenceLevel.SMOKE
            and self.claim_scope is ClaimScope.SCIENTIFIC_EFFECTIVENESS
        ):
            raise ValueError("smoke evidence cannot claim scientific effectiveness")
        if not self.human_approval_required:
            raise ValueError("Wiki publication always requires human approval")
        return self


class KnowledgeVersionTransition(VersionedModel):
    previous: WikiEntryCandidate
    current: WikiEntryCandidate

    @model_validator(mode="after")
    def transition_preserves_supersession(self) -> Self:
        if self.previous.validity_status is not KnowledgeValidity.SUPERSEDED:
            raise ValueError("previous Wiki version must be marked SUPERSEDED")
        if self.current.version != self.previous.version + 1:
            raise ValueError("Wiki version must increment by one")
        if self.previous.candidate_id not in self.current.supersedes:
            raise ValueError("current Wiki version must reference the previous version")
        return self


class WikiInvalidationRecord(VersionedModel):
    record_id: Identifier
    candidate_id: Identifier
    invalidated_version: int = Field(ge=1)
    reason: ShortText
    evidence_ref: ArtifactRef
    invalidated_at: datetime


class SkillReplayReport(VersionedModel):
    report_id: Identifier
    candidate_id: Identifier
    baseline_run_id: Identifier
    replay_run_id: Identifier
    isolation_environment_ref: ArtifactRef
    baseline_validation_ref: ArtifactRef
    replay_validation_ref: ArtifactRef
    comparison_decision: DecisionRecord
    checks: dict[str, bool]
    status: ResultStatus

    @model_validator(mode="after")
    def valid_replay_requires_all_gates(self) -> Self:
        if self.baseline_run_id == self.replay_run_id:
            raise ValueError("Skill replay must be independent from its baseline")
        if self.status is ResultStatus.VALID:
            if not self.checks or not all(self.checks.values()):
                raise ValueError("valid Skill replay requires every gate to pass")
            if self.comparison_decision.status is not DecisionStatus.ACCEPT:
                raise ValueError("valid Skill replay requires baseline improvement")
        return self


class PublishedSkill(VersionedModel):
    skill_id: Identifier
    version: int = Field(ge=1)
    candidate: KnowledgeCandidate
    replay_report: SkillReplayReport
    approval: ApprovalRecord
    supersedes: tuple[str, ...] = ()
    validity_status: KnowledgeValidity = KnowledgeValidity.VALID

    @model_validator(mode="after")
    def publication_requires_replay_and_scoped_human_approval(self) -> Self:
        if self.candidate.kind is not KnowledgeKind.SKILL:
            raise ValueError("only Skill candidates can be published as Skills")
        if self.replay_report.candidate_id != self.candidate.candidate_id:
            raise ValueError("Skill replay report must match its candidate")
        if self.replay_report.status is not ResultStatus.VALID:
            raise ValueError("Skill publication requires a valid replay report")
        if self.approval.kind is not ApprovalKind.SKILL_PROMOTION:
            raise ValueError("Skill publication requires SKILL_PROMOTION approval")
        if self.approval.decision is not ApprovalDecision.APPROVED:
            raise ValueError("Skill publication requires an approved decision")
        expected_scope = f"skill:{self.candidate.candidate_id}"
        if self.approval.scope != expected_scope:
            raise ValueError("Skill approval scope must match its candidate")
        if self.validity_status is not KnowledgeValidity.VALID:
            raise ValueError("newly published Skill must start VALID")
        return self

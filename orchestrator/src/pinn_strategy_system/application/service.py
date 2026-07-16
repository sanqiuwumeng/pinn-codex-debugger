"""Application services consumed by the operator CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from langgraph.types import Command

from pinn_strategy_system.assurance import (
    EvaluationBasisService,
    ExperimentGovernanceService,
    PhysicalAuditService,
)
from pinn_strategy_system.contracts import (
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    AuditStatus,
    ExperimentCompletenessReport,
    ExperimentDraft,
    PhysicalAuditReport,
    ResultStatus,
    RunManifest,
    RunSubmissionStatus,
    WorkflowIntent,
    WorkflowStage,
    WorkflowStateEnvelope,
)
from pinn_strategy_system.execution import (
    ExecutionBackend,
    ManifestFirstRunner,
    SQLiteRunRegistry,
)
from pinn_strategy_system.orchestration import build_phase0_graph
from pinn_strategy_system.storage import SQLiteCheckpointStore

from .catalog import SQLiteWorkflowCatalog
from .contracts import ApplicationResult, OperationOutcome, OperatorCase


class ExecutionBackendFactory(Protocol):
    def __call__(self, profile_path: Path) -> ExecutionBackend: ...


@dataclass(frozen=True)
class _AuditBundle:
    physical: PhysicalAuditReport
    experiment: ExperimentCompletenessReport
    evaluation_basis_ready: bool
    evaluation_basis_checks: dict[str, bool]
    evaluation_basis_reasons: tuple[str, ...]


class OperatorApplicationService:
    def __init__(
        self,
        *,
        runtime_root: Path,
        backend_factory: ExecutionBackendFactory,
    ) -> None:
        if not runtime_root.is_absolute():
            raise ValueError("operator runtime root must be absolute")
        self._runtime_root = runtime_root.resolve(strict=False)
        self._runtime_root.mkdir(parents=True, exist_ok=True)
        workflow_root = self._runtime_root / "workflows"
        execution_root = self._runtime_root / "execution"
        workflow_root.mkdir(exist_ok=True)
        execution_root.mkdir(exist_ok=True)
        self._checkpoint_store = SQLiteCheckpointStore(
            workflow_root / "checkpoints.sqlite3"
        )
        self._catalog = SQLiteWorkflowCatalog(
            workflow_root / "catalog.sqlite3"
        )
        self._run_registry_path = execution_root / "runs.sqlite3"
        self._backend_factory = backend_factory
        self._physical = PhysicalAuditService()
        self._experiments = ExperimentGovernanceService()
        self._evaluation_basis = EvaluationBasisService()

    def audit(self, *, case: OperatorCase, case_path: Path) -> ApplicationResult:
        return self._evaluate_case(
            command="audit",
            case=case,
            case_path=case_path,
        )

    def plan(self, *, case: OperatorCase, case_path: Path) -> ApplicationResult:
        return self._evaluate_case(
            command="plan",
            case=case,
            case_path=case_path,
        )

    def smoke(self, workflow_id: str) -> ApplicationResult:
        return self._execute(workflow_id, WorkflowIntent.SMOKE)

    def full(self, workflow_id: str) -> ApplicationResult:
        return self._execute(workflow_id, WorkflowIntent.FULL_RUN)

    def status(self, workflow_id: str) -> ApplicationResult:
        return self._execution_status(workflow_id, command="status", reconcile=True)

    def replay(self, workflow_id: str) -> ApplicationResult:
        result = self._execution_status(
            workflow_id,
            command="replay",
            reconcile=True,
        )
        return result.model_copy(
            update={"data": {**result.data, "zero_relaunch_replay": True}}
        )

    def _evaluate_case(
        self,
        *,
        command: str,
        case: OperatorCase,
        case_path: Path,
    ) -> ApplicationResult:
        self._catalog.register(case, case_path)
        bundle = self._audit_bundle(case)
        specification = bundle.experiment.experiment_spec
        envelope = WorkflowStateEnvelope(
            workflow_id=case.request.workflow_id,
            request=case.request,
            physical_audit=bundle.physical,
            metric_contract=case.metric_contract,
            model_evaluation=(
                case.model_evaluation if bundle.evaluation_basis_ready else None
            ),
            experiment_spec=specification,
            approvals=case.approvals,
            smoke_validation_status=case.smoke_validation_status,
        )
        config = _graph_config(case.request.workflow_id)
        with self._checkpoint_store.open() as checkpointer:
            graph = build_phase0_graph(checkpointer)
            snapshot = graph.get_state(config)
            if not snapshot.values:
                state = graph.invoke(envelope.to_state(), config)
            else:
                state = dict(snapshot.values)
                for _ in range(8):
                    resume = _resume_payload(state, case, bundle)
                    if resume is None:
                        break
                    previous_stage = state.get("stage")
                    state = graph.invoke(Command(resume=resume), config)
                    if state.get("stage") == previous_stage:
                        break
        stage = WorkflowStage(state["stage"])
        outcome = _stage_outcome(stage)
        result = ApplicationResult(
            command=command,
            outcome=outcome,
            code=stage.value,
            message=state.get("last_transition_reason") or _stage_message(stage),
            workflow_id=case.request.workflow_id,
            stage=stage.value,
            data={
                "unresolved": _unresolved(stage, case, bundle),
                "physical_audit": bundle.physical.model_dump(mode="json"),
                "evaluation_basis": {
                    "ready": bundle.evaluation_basis_ready,
                    "checks": bundle.evaluation_basis_checks,
                    "reasons": list(bundle.evaluation_basis_reasons),
                },
                "experiment_completeness": bundle.experiment.model_dump(
                    mode="json"
                ),
                "case_path": str(case_path),
            },
        )
        self._catalog.record_result(result)
        return result

    def _execute(
        self,
        workflow_id: str,
        intent: WorkflowIntent,
    ) -> ApplicationResult:
        case = self._catalog.load(workflow_id)
        if case.request.intent is not intent:
            return self._record(
                ApplicationResult(
                    command=_intent_command(intent),
                    outcome=OperationOutcome.GATE_REJECTED,
                    code="INTENT_MISMATCH",
                    message="Persisted workflow intent does not match the command.",
                    workflow_id=workflow_id,
                    data={},
                )
            )
        bundle = self._audit_bundle(case)
        if bundle.experiment.status is not AuditStatus.PASS:
            return self._record(
                ApplicationResult(
                    command=_intent_command(intent),
                    outcome=OperationOutcome.NEEDS_INPUT,
                    code="NEEDS_EXPERIMENT_EVIDENCE",
                    message="A complete single-intervention experiment is required.",
                    workflow_id=workflow_id,
                    stage=WorkflowStage.NEEDS_EXPERIMENT_EVIDENCE.value,
                    data={
                        "unresolved": bundle.experiment.model_dump(mode="json")
                    },
                )
            )
        stage = self._workflow_stage(workflow_id)
        required_stage = (
            WorkflowStage.SMOKE_APPROVED
            if intent is WorkflowIntent.SMOKE
            else WorkflowStage.FULL_APPROVED
        )
        if stage is not required_stage:
            return self._record(
                ApplicationResult(
                    command=_intent_command(intent),
                    outcome=(
                        OperationOutcome.GATE_REJECTED
                        if stage in {
                            WorkflowStage.REJECTED,
                            WorkflowStage.RESULT_INVALID,
                        }
                        else OperationOutcome.NEEDS_INPUT
                    ),
                    code=stage.value,
                    message="Workflow gate does not authorize execution.",
                    workflow_id=workflow_id,
                    stage=stage.value,
                    data={"unresolved": _unresolved(stage, case, bundle)},
                )
            )
        if intent is WorkflowIntent.FULL_RUN:
            if case.smoke_validation_status is not ResultStatus.VALID:
                raise RuntimeError("FULL_APPROVED state lacks validated smoke")
            _require_approval(case.approvals, ApprovalKind.FULL_RUN)
        manifest = (
            case.smoke_manifest
            if intent is WorkflowIntent.SMOKE
            else case.full_manifest
        )
        if manifest is None:
            return self._record(
                ApplicationResult(
                    command=_intent_command(intent),
                    outcome=OperationOutcome.NEEDS_INPUT,
                    code="NEEDS_RUN_MANIFEST",
                    message="Execution requires an explicit run manifest.",
                    workflow_id=workflow_id,
                    stage=stage.value,
                    data={},
                )
            )
        _require_manifest_paths(manifest)
        approval = _require_approval(case.approvals, ApprovalKind.EXPERIMENT)
        if case.execution_profile_path is None:
            return self._record(
                ApplicationResult(
                    command=_intent_command(intent),
                    outcome=OperationOutcome.NEEDS_INPUT,
                    code="NEEDS_EXECUTION_PROFILE",
                    message="Execution requires an explicit runtime profile.",
                    workflow_id=workflow_id,
                    stage=stage.value,
                    data={},
                )
            )
        backend = self._backend_factory(case.execution_profile_path)
        runner = ManifestFirstRunner(
            SQLiteRunRegistry(self._run_registry_path),
            backend,
        )
        submission = runner.submit(manifest, approval)
        result = ApplicationResult(
            command=_intent_command(intent),
            outcome=OperationOutcome.SUCCESS,
            code=submission.status.value,
            message="Governed run submission was accepted.",
            workflow_id=workflow_id,
            stage=stage.value,
            data={"run_submission": submission.model_dump(mode="json")},
        )
        return self._record(result)

    def _execution_status(
        self,
        workflow_id: str,
        *,
        command: str,
        reconcile: bool,
    ) -> ApplicationResult:
        case = self._catalog.load(workflow_id)
        stage = self._workflow_stage(workflow_id)
        manifest = _manifest_for_case(case)
        submission = None
        if manifest is not None and self._run_registry_path.exists():
            registry = SQLiteRunRegistry(self._run_registry_path)
            submission = registry.lookup(manifest.idempotency_key)
            if (
                reconcile
                and submission is not None
                and submission.status
                in {
                    RunSubmissionStatus.RUNNING,
                    RunSubmissionStatus.RUNNING_UNKNOWN,
                    RunSubmissionStatus.CANCELLING,
                }
                and case.execution_profile_path is not None
            ):
                runner = ManifestFirstRunner(
                    registry,
                    self._backend_factory(case.execution_profile_path),
                )
                submission = runner.reconcile(manifest.idempotency_key)
        if submission is not None and submission.status is RunSubmissionStatus.FAILED:
            outcome = OperationOutcome.RUN_FAILED
        elif submission is None and stage.value.startswith("NEEDS_"):
            outcome = OperationOutcome.NEEDS_INPUT
        elif stage in {WorkflowStage.REJECTED, WorkflowStage.RESULT_INVALID}:
            outcome = OperationOutcome.GATE_REJECTED
        else:
            outcome = OperationOutcome.SUCCESS
        result = ApplicationResult(
            command=command,
            outcome=outcome,
            code=(submission.status.value if submission else stage.value),
            message="Persisted workflow and execution status were reconciled.",
            workflow_id=workflow_id,
            stage=stage.value,
            data={
                "run_submission": (
                    submission.model_dump(mode="json") if submission else None
                )
            },
        )
        return self._record(result)

    def _audit_bundle(self, case: OperatorCase) -> _AuditBundle:
        physical = self._physical.audit(
            report_id=f"physical-{case.case_id}",
            unit_system=case.unit_system,
            parameters=case.parameters,
            equations=case.equations,
            derivative_scaling=case.derivative_scaling,
        )
        experiment = self._experiments.audit(
            report_id=f"experiment-{case.case_id}",
            draft=(case.experiment_draft or _empty_draft(case)),
        )
        basis = self._evaluation_basis.validate(
            authority=case.physical_model,
            references=case.references,
        )
        return _AuditBundle(
            physical=physical,
            experiment=experiment,
            evaluation_basis_ready=basis.ready,
            evaluation_basis_checks=basis.checks,
            evaluation_basis_reasons=basis.reasons,
        )

    def _workflow_stage(self, workflow_id: str) -> WorkflowStage:
        with self._checkpoint_store.open() as checkpointer:
            graph = build_phase0_graph(checkpointer)
            snapshot = graph.get_state(_graph_config(workflow_id))
        if not snapshot.values:
            raise KeyError("workflow has no persisted graph state")
        return WorkflowStage(snapshot.values["stage"])

    def _record(self, result: ApplicationResult) -> ApplicationResult:
        self._catalog.record_result(result)
        return result


def _empty_draft(case: OperatorCase):
    return ExperimentDraft(
        experiment_id=f"unresolved-{case.case_id}",
        project_id=case.request.project_id,
    )


def _graph_config(workflow_id: str) -> dict:
    return {"configurable": {"thread_id": workflow_id}}


def _resume_payload(state: dict, case: OperatorCase, bundle: _AuditBundle):
    stage = WorkflowStage(state["stage"])
    if stage is WorkflowStage.NEEDS_UNIT_CONFIRMATION:
        if bundle.physical.status in {
            AuditStatus.PASS,
            AuditStatus.WARN,
            AuditStatus.REJECT,
        }:
            return {"physical_audit": bundle.physical.model_dump(mode="json")}
        return None
    if stage is WorkflowStage.NEEDS_UNIT_WARNING_APPROVAL:
        approval = _find_approval(case.approvals, ApprovalKind.UNIT_WARNING)
        return None if approval is None else {"approval": approval.model_dump(mode="json")}
    if stage is WorkflowStage.NEEDS_METRIC_PRIORITY:
        approval = _find_approval(case.approvals, ApprovalKind.METRIC_PRIORITY)
        if case.metric_contract is None or approval is None:
            return None
        return {
            "metric_contract": case.metric_contract.model_dump(mode="json"),
            "approval": approval.model_dump(mode="json"),
        }
    if stage is WorkflowStage.NEEDS_DIAGNOSTIC_EVIDENCE:
        if not bundle.evaluation_basis_ready or case.model_evaluation is None:
            return None
        return {"model_evaluation": case.model_evaluation.model_dump(mode="json")}
    if stage is WorkflowStage.NEEDS_EXPERIMENT_EVIDENCE:
        if bundle.experiment.experiment_spec is None:
            return None
        return {
            "experiment_spec": bundle.experiment.experiment_spec.model_dump(
                mode="json"
            )
        }
    approval_kind = {
        WorkflowStage.NEEDS_EXPERIMENT_APPROVAL: ApprovalKind.EXPERIMENT,
        WorkflowStage.NEEDS_FULL_RUN_APPROVAL: ApprovalKind.FULL_RUN,
    }.get(stage)
    if approval_kind is None:
        return None
    approval = _find_approval(case.approvals, approval_kind)
    return None if approval is None else {"approval": approval.model_dump(mode="json")}


def _unresolved(stage: WorkflowStage, case: OperatorCase, bundle: _AuditBundle):
    if stage is WorkflowStage.NEEDS_UNIT_CONFIRMATION:
        return [item.model_dump(mode="json") for item in bundle.physical.findings]
    if stage is WorkflowStage.NEEDS_UNIT_WARNING_APPROVAL:
        return {"approval_kind": ApprovalKind.UNIT_WARNING.value}
    if stage is WorkflowStage.NEEDS_METRIC_PRIORITY:
        missing = []
        if case.metric_contract is None:
            missing.append("metric_contract")
        if _find_approval(case.approvals, ApprovalKind.METRIC_PRIORITY) is None:
            missing.append("metric_priority_approval")
        return missing
    if stage is WorkflowStage.NEEDS_DIAGNOSTIC_EVIDENCE:
        return {
            "evaluation_basis_reasons": list(bundle.evaluation_basis_reasons),
            "model_evaluation_missing": case.model_evaluation is None,
        }
    if stage is WorkflowStage.NEEDS_EXPERIMENT_EVIDENCE:
        return bundle.experiment.model_dump(mode="json")
    if stage is WorkflowStage.NEEDS_EXPERIMENT_APPROVAL:
        return {"approval_kind": ApprovalKind.EXPERIMENT.value}
    if stage is WorkflowStage.NEEDS_SMOKE_VALIDATION:
        return {"smoke_validation_status": case.smoke_validation_status.value}
    if stage is WorkflowStage.NEEDS_FULL_RUN_APPROVAL:
        return {"approval_kind": ApprovalKind.FULL_RUN.value}
    return []


def _stage_outcome(stage: WorkflowStage) -> OperationOutcome:
    if stage.value.startswith("NEEDS_"):
        return OperationOutcome.NEEDS_INPUT
    if stage in {WorkflowStage.REJECTED, WorkflowStage.RESULT_INVALID}:
        return OperationOutcome.GATE_REJECTED
    return OperationOutcome.SUCCESS


def _stage_message(stage: WorkflowStage) -> str:
    return f"Workflow reached {stage.value}."


def _intent_command(intent: WorkflowIntent) -> str:
    return "smoke" if intent is WorkflowIntent.SMOKE else "full"


def _find_approval(
    approvals: tuple[ApprovalRecord, ...],
    kind: ApprovalKind,
) -> ApprovalRecord | None:
    matching = tuple(item for item in approvals if item.kind is kind)
    return matching[-1] if matching else None


def _require_approval(
    approvals: tuple[ApprovalRecord, ...],
    kind: ApprovalKind,
) -> ApprovalRecord:
    approval = _find_approval(approvals, kind)
    if approval is None or approval.decision is not ApprovalDecision.APPROVED:
        raise RuntimeError("persisted approval gate is not satisfied")
    return approval


def _manifest_for_case(case: OperatorCase) -> RunManifest | None:
    return (
        case.smoke_manifest
        if case.request.intent is WorkflowIntent.SMOKE
        else case.full_manifest
        if case.request.intent is WorkflowIntent.FULL_RUN
        else None
    )


def _require_manifest_paths(manifest: RunManifest) -> None:
    values = (
        manifest.interpreter,
        manifest.working_directory,
        manifest.output_root,
    )
    if any(not _is_absolute(value) for value in values):
        raise ValueError("run manifest paths must be absolute")


def _is_absolute(value: str) -> bool:
    return Path(value).is_absolute() or PurePosixPath(value).is_absolute()

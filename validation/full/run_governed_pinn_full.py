"""Run and replay one full PINN reproducibility experiment.

The immutable historical uniform full result is the baseline. The active
focused-collocation source is staged read-only and rerun in an exact-version
environment. This adapter collects evidence; it does not weaken universal
assurance gates or modify the source case.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
CASE_ADAPTER_ROOT = REPOSITORY_ROOT / "validation" / "cases"
SMOKE_ADAPTER_ROOT = REPOSITORY_ROOT / "validation" / "smoke"
sys.path.insert(0, str(ORCHESTRATOR_SRC))
sys.path.insert(0, str(CASE_ADAPTER_ROOT))
sys.path.insert(0, str(SMOKE_ADAPTER_ROOT))

from pinn_strategy_system.assurance import (  # noqa: E402
    ExperimentGovernanceService,
    RunValidationService,
)
from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactRef,
    AuditStatus,
    BudgetSpec,
    DecisionRecord,
    DecisionStatus,
    ExperimentDraft,
    InterventionChange,
    MetricEvidenceBasis,
    ModelEvaluationReport,
    PhysicalAuditReport,
    ResultStatus,
    RunManifest,
    RunValidationInput,
    SourceRef,
)
from pinn_strategy_system.execution import (  # noqa: E402
    ManifestFirstRunner,
    SQLiteRunRegistry,
)
from pinn_strategy_system.storage import (  # noqa: E402
    AppendOnlyAuditStore,
    LocalArtifactStore,
    StoreLayout,
)
from read_only_pinn_case import run_case  # noqa: E402
from run_governed_pinn_smoke import (  # noqa: E402
    EXPECTED_OUTPUTS,
    ForbiddenReplayBackend,
    _artifact,
    _build_local_backend,
    _environment_manifest,
    _run_one,
    _sha256,
    _source_snapshot,
    _stage_case,
    _verify_artifact_reference,
)

WORKFLOW_ID = "pinn2d-focused-full-repro-20260716"
EXPERIMENT_ID = "focused-collocation-full-repro-20260716"
RUN_ID = "pinn2d-focused-full-repro-20260716"
OUTPUT_TAG = "candidate_focused_full_repro_20260716"
BASELINE_TAG = "baseline_uniform_full_immutable"
EXPERIMENT_APPROVAL_ID = "approval-focused-full-experiment-20260716"
FULL_APPROVAL_ID = "approval-standing-full-run-20260716"


def _write_json_no_overwrite(path: Path, payload: Any) -> ArtifactRef:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.write("\n")
    return _artifact(path.stem, path)


def _approval_path() -> Path:
    return (
        REPOSITORY_ROOT
        / "openspec"
        / "changes"
        / "build-rag-multi-agent-dl-strategy-system"
        / "approval-records"
        / "2026-07-16-standing-full-run-authorization.md"
    )


def _approvals(approval_ref: ArtifactRef) -> tuple[ApprovalRecord, ApprovalRecord]:
    experiment = ApprovalRecord(
        approval_id=EXPERIMENT_APPROVAL_ID,
        workflow_id=WORKFLOW_ID,
        kind=ApprovalKind.EXPERIMENT,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=datetime(2026, 7, 16, tzinfo=UTC),
        scope="full reproducibility experiment for the focused-collocation candidate",
        evidence_refs=(approval_ref,),
    )
    full = ApprovalRecord(
        approval_id=FULL_APPROVAL_ID,
        workflow_id=WORKFLOW_ID,
        kind=ApprovalKind.FULL_RUN,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=datetime(2026, 7, 16, tzinfo=UTC),
        scope="standing full-run and remote execution authorization",
        evidence_refs=(approval_ref,),
    )
    return experiment, full


def _full_environment(training_python: Path) -> dict[str, Any]:
    payload = _environment_manifest(training_python)
    if payload["numpy"] != "2.2.5":
        raise RuntimeError("full reproducibility run requires NumPy 2.2.5")
    completed = subprocess.run(
        (str(training_python), "-m", "pip", "freeze", "--all"),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload["pip_freeze"] = tuple(
        line for line in completed.stdout.splitlines() if line.strip()
    )
    return payload


def _full_manifest(
    *,
    workspace: Path,
    training_python: Path,
    config_ref: ArtifactRef,
) -> RunManifest:
    return RunManifest(
        run_id=RUN_ID,
        workflow_id=WORKFLOW_ID,
        experiment_id=EXPERIMENT_ID,
        idempotency_key=f"{EXPERIMENT_ID}-full-3000-seed42",
        environment_name="pinn_full_repro_20260716",
        interpreter=str(training_python),
        working_directory=str(workspace),
        command=(
            str(training_python),
            str(workspace / "run_benchmark.py"),
            "--mode",
            "full",
            "--output-tag",
            OUTPUT_TAG,
        ),
        config_ref=config_ref,
        output_root=str(workspace / "outputs" / OUTPUT_TAG),
        expected_artifacts=EXPECTED_OUTPUTS,
        checkpoint_policy="Persist the full model and reproducibility manifest.",
        rollback_plan="Keep the immutable uniform baseline active when any gate fails.",
    )


def execute(*, case_root: Path, training_python: Path, output_root: Path) -> None:
    case_root = case_root.resolve(strict=True)
    training_python = training_python.resolve(strict=True)
    output_root = output_root.resolve(strict=False)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite full-run root: {output_root}")
    output_root.mkdir(parents=True)

    original_snapshot = _source_snapshot(case_root)
    workspace = output_root / "workspace"
    _stage_case(case_root, workspace, case_root / "pinn_model.py")
    baseline_source = case_root / "outputs" / "full"
    baseline_copy = workspace / "outputs" / BASELINE_TAG
    baseline_copy.parent.mkdir()
    shutil.copytree(baseline_source, baseline_copy)

    knowledge_root = output_root / "knowledge-source"
    knowledge_root.mkdir()
    layout = StoreLayout.provision(
        runtime_root=output_root / "runtime",
        knowledge_source_root=knowledge_root,
    )
    artifact_store = LocalArtifactStore(layout.artifact_root)
    audit = AppendOnlyAuditStore(layout.audit_database)
    backend_run_root = output_root / "backend-runs"
    backend_run_root.mkdir()
    collection_root = output_root / "collected-runs"
    collection_root.mkdir()

    source_ref = artifact_store.put_json(
        "source-snapshot",
        {
            "case_root": str(case_root),
            "source_hashes": original_snapshot,
            "staged_candidate_model_sha256": _sha256(workspace / "pinn_model.py"),
            "single_intervention": "sample_fixed_collocation",
        },
    )
    environment_payload = _full_environment(training_python)
    environment_ref = artifact_store.put_json(
        "full-training-environment",
        environment_payload,
    )
    approval_ref = _artifact("standing-full-run-approval", _approval_path())
    experiment_approval, full_approval = _approvals(approval_ref)
    prior_report_path = (
        REPOSITORY_ROOT
        / "validation"
        / "cases"
        / "read-only-general-pinn-case-final-2026-07-16.json"
    )
    prior_report = json.loads(prior_report_path.read_text(encoding="utf-8"))
    prior_report_ref = _artifact("prior-accepted-full-comparison", prior_report_path)
    smoke_report_path = (
        REPOSITORY_ROOT
        / "validation"
        / "smoke"
        / "results"
        / "universal-pinn-smoke-20260716"
        / "smoke-execution-report.json"
    )
    smoke_report_ref = _artifact("undertrained-smoke-evidence", smoke_report_path)
    baseline_field_ref = _artifact(
        "immutable-uniform-full-aligned-fields",
        baseline_copy / "data" / "aligned_fields.npz",
    )
    authority_ref = _artifact(
        "pinn2d-physical-model-authority",
        workspace / "physics.py",
    )
    metric_contract_ref = artifact_store.put_json(
        "metric-contract",
        prior_report["metric_gate"]["contract"],
    )

    draft = ExperimentDraft(
        experiment_id=EXPERIMENT_ID,
        project_id="pinn-2d-validation-case",
        observed_failure_mechanism="early interface and localized maximum error in the historical full baseline",
        supporting_evidence_refs=(prior_report_ref, smoke_report_ref),
        interventions=(
            InterventionChange(
                target="sample_fixed_collocation",
                before={"uniform_fraction": 1.0, "focused_fraction": 0.0},
                after={"uniform_fraction": 0.875, "focused_fraction": 0.125},
                rationale="Reproduce the previously accepted full focused-collocation result in an exact environment.",
                source_ref=SourceRef(
                    uri=(workspace / "pinn_model.py").as_uri(),
                    sha256=_sha256(workspace / "pinn_model.py"),
                    symbol="sample_fixed_collocation",
                ),
            ),
        ),
        unchanged_controls=(
            "physics and unit system",
            "network architecture",
            "optimizer and learning rate",
            "3000 epochs and 20000 collocation points",
            "FEM discretization",
            "random seed 42",
        ),
        expected_primary_metric_movement={
            "max_abs": "decrease",
            "rmse": "decrease if max_abs is tied",
        },
        guardrail_limits={
            "mae_absolute_regression_K": 1.0,
            "mae_relative_regression": 0.10,
        },
        smoke_budget=BudgetSpec(
            max_steps=8,
            resource_description="completed under-trained workflow smoke retained as evidence",
        ),
        full_budget=BudgetSpec(
            max_steps=3000,
            max_seconds=1800,
            resource_description="local exact-version CPU full reproducibility run",
        ),
        falsification_condition="Reject or roll back when the full metric contract or any provenance gate fails.",
        rollback_plan="Keep the immutable uniform baseline active and preserve rejected evidence.",
        source_snapshot_ref=source_ref,
        dataset_refs=(baseline_field_ref, authority_ref),
        environment_ref=environment_ref,
        random_seed=42,
        baseline_run_ref=prior_report_ref,
        metric_contract_ref=metric_contract_ref,
        output_root=str(output_root),
        checkpoint_policy="Persist approval, environment, source and run manifests before launch; save the full checkpoint.",
        expected_artifacts=EXPECTED_OUTPUTS,
    )
    completeness = ExperimentGovernanceService().audit(
        report_id="pinn2d-full-completeness",
        draft=draft,
    )
    if completeness.status is not AuditStatus.PASS:
        raise RuntimeError(f"full experiment completeness failed: {completeness}")
    assert completeness.experiment_spec is not None
    experiment_ref = artifact_store.put_json(
        "full-experiment-spec",
        completeness.experiment_spec.model_dump(mode="json"),
    )
    approval_state_ref = artifact_store.put_json(
        "full-workflow-approved",
        {
            "workflow_id": WORKFLOW_ID,
            "stage": "FULL_APPROVED_DIAGNOSTIC_REPRODUCTION",
            "experiment_approval": experiment_approval.model_dump(mode="json"),
            "full_approval": full_approval.model_dump(mode="json"),
            "experiment_spec_ref": experiment_ref.model_dump(mode="json"),
            "undertrained_smoke_decision": "REJECT",
            "promotion_policy": "full evidence must pass post-run gates",
        },
    )
    manifest = _full_manifest(
        workspace=workspace,
        training_python=training_python,
        config_ref=_artifact("full-config-code", workspace / "config.py"),
    )
    manifest_ref = artifact_store.put_json(
        "full-run-manifest",
        manifest.model_dump(mode="json"),
    )

    registry = SQLiteRunRegistry(
        layout.tracking_database.parent / "launch_registry.sqlite3"
    )
    backend = _build_local_backend(backend_run_root)
    completed_run = _run_one(
        manifest=manifest,
        approval=experiment_approval,
        runner=ManifestFirstRunner(registry, backend),
        audit=audit,
        output_directory=workspace / "outputs" / OUTPUT_TAG,
        collection_directory=collection_root / RUN_ID,
    )
    if completed_run.exit_code != 0:
        raise RuntimeError("full process failed; evidence was preserved")

    analysis = run_case(
        case_root=workspace,
        baseline_name=BASELINE_TAG,
        candidate_name=OUTPUT_TAG,
    )
    analysis_ref = artifact_store.put_json("full-analysis", analysis)
    decision_status = DecisionStatus(analysis["metric_gate"]["status"])
    candidate_metrics = analysis["prediction_analysis"]["candidate_global_metrics"]
    physical = PhysicalAuditReport(
        report_id="pinn2d-full-physical-audit",
        unit_system_id="pinn-2d-test-case-si",
        status=AuditStatus(analysis["physical_audit"]["status"]),
        source_files_unchanged=analysis["physical_audit"]["source_files_unchanged"],
    )
    evaluation = ModelEvaluationReport(
        report_id="pinn2d-full-model-evaluation",
        status=ResultStatus(analysis["prediction_analysis"]["status"]),
        physical_model_authority_ref=authority_ref,
        metric_values={name: float(value) for name, value in candidate_metrics.items()},
        metric_bases={
            name: MetricEvidenceBasis.REFERENCE_EVIDENCE
            for name in candidate_metrics
        },
        prediction_analysis_ref=analysis_ref,
        diagnostic_refs=(completed_run.artifacts["data/aligned_fields.npz"],),
        domain_provider_ids=("heat-transfer.phase-change.v1",),
        checks={
            "physical_audit": analysis["physical_audit"]["status"] == "PASS",
            "evaluation_basis": analysis["case_scope"]["evaluation_basis"]["ready"],
            "field_alignment": analysis["prediction_analysis"]["status"] == "RESULT_VALID",
            "source_integrity": analysis["read_only"]["all_observed_sources_unchanged"],
        },
    )
    decision = DecisionRecord(
        decision_id="pinn2d-full-metric-decision",
        status=decision_status,
        observed_failure_mechanism="localized full-run error against the case numerical reference",
        selected_intervention=(
            "12.5 percent focused collocation"
            if decision_status is DecisionStatus.ACCEPT
            else None
        ),
        unchanged_controls=completeness.experiment_spec.unchanged_controls,
        supporting_evidence_refs=(analysis_ref,),
        expected_primary_metric_movement=completeness.experiment_spec.expected_primary_metric_movement,
        guardrail_limits=completeness.experiment_spec.guardrail_limits,
        falsification_condition=completeness.experiment_spec.falsification_condition,
        rollback_plan=completeness.experiment_spec.rollback_plan,
        reasons=tuple(analysis["metric_gate"]["reasons"]),
    )
    validation = RunValidationService().validate(
        report_id="pinn2d-full-run-validation",
        validation_input=RunValidationInput(
            run_id=RUN_ID,
            process_exit_code=completed_run.exit_code,
            physical_audit=physical,
            model_evaluation=evaluation,
            metric_decision=decision,
            required_artifacts=EXPECTED_OUTPUTS,
            produced_artifacts=completed_run.artifacts,
            run_manifest_ref=manifest_ref,
            source_snapshot_ref=source_ref,
            dataset_refs=(baseline_field_ref, authority_ref),
            environment_ref=environment_ref,
            random_seed=42,
        ),
    )
    validation_ref = artifact_store.put_json(
        "full-run-validation",
        validation.model_dump(mode="json"),
    )
    source_unchanged = original_snapshot == _source_snapshot(case_root)
    rollback_required = (
        completed_run.monitoring["outcome"] != "COMPLETED"
        or decision_status is not DecisionStatus.ACCEPT
        or validation.status is not ResultStatus.VALID
        or not source_unchanged
    )
    completed_state_ref = artifact_store.put_json(
        "full-workflow-completed",
        {
            "workflow_id": WORKFLOW_ID,
            "stage": "FULL_VALIDATED" if not rollback_required else "FULL_ROLLED_BACK",
            "decision": decision.model_dump(mode="json"),
            "validation_ref": validation_ref.model_dump(mode="json"),
            "rollback_required": rollback_required,
        },
    )
    evidence_manifest = {
        "source_snapshot": source_ref.model_dump(mode="json"),
        "environment": environment_ref.model_dump(mode="json"),
        "approval_state": approval_state_ref.model_dump(mode="json"),
        "completed_state": completed_state_ref.model_dump(mode="json"),
        "experiment_spec": experiment_ref.model_dump(mode="json"),
        "run_manifest": manifest_ref.model_dump(mode="json"),
        "baseline_fields": baseline_field_ref.model_dump(mode="json"),
        "analysis": analysis_ref.model_dump(mode="json"),
        "validation": validation_ref.model_dump(mode="json"),
        "outputs": {
            name: artifact.model_dump(mode="json")
            for name, artifact in completed_run.artifacts.items()
        },
    }
    evidence_ref = artifact_store.put_json(
        "full-evidence-manifest",
        evidence_manifest,
    )
    report = {
        "workflow_id": WORKFLOW_ID,
        "scope": "full reproducibility evidence; no automatic model publication",
        "execution_location": "local exact-version full-repro sandbox",
        "environment": {
            key: environment_payload[key]
            for key in (
                "python",
                "torch",
                "numpy",
                "scipy",
                "matplotlib",
                "cuda_available",
                "executable",
            )
        },
        "process": {
            "submission": completed_run.submission,
            "exit_code": completed_run.exit_code,
            "monitoring": completed_run.monitoring,
        },
        "localized_analysis": analysis["prediction_analysis"],
        "metric_decision": decision.model_dump(mode="json"),
        "validation": validation.model_dump(mode="json"),
        "rollback_evaluation": {
            "required": rollback_required,
            "action": (
                "keep immutable uniform baseline active; do not promote candidate"
                if rollback_required
                else "candidate full evidence is valid; publication remains a separate governed action"
            ),
        },
        "source_case_unchanged": source_unchanged,
        "evidence_manifest_ref": evidence_ref.model_dump(mode="json"),
        "replay_status": "PENDING",
    }
    report_path = output_root / "full-execution-report.json"
    _write_json_no_overwrite(report_path, report)
    print(
        json.dumps(
            {
                "report": str(report_path),
                "decision": decision_status.value,
                "validation": validation.status.value,
                "rollback_required": rollback_required,
                "source_unchanged": source_unchanged,
            },
            ensure_ascii=False,
        )
    )


def _read_artifact(artifact_root: Path, artifact_id: str) -> dict[str, Any]:
    return json.loads(
        (artifact_root / f"{artifact_id}.json").read_text(encoding="utf-8")
    )


def replay(*, output_root: Path) -> None:
    output_root = output_root.resolve(strict=True)
    layout = StoreLayout.provision(
        runtime_root=output_root / "runtime",
        knowledge_source_root=output_root / "knowledge-source",
    )
    manifest = RunManifest.model_validate(
        _read_artifact(layout.artifact_root, "full-run-manifest")
    )
    approval_ref = _artifact("standing-full-run-approval", _approval_path())
    experiment_approval, _ = _approvals(approval_ref)
    backend = ForbiddenReplayBackend()
    registry = SQLiteRunRegistry(
        layout.tracking_database.parent / "launch_registry.sqlite3"
    )
    submission = ManifestFirstRunner(registry, backend).submit(
        manifest,
        experiment_approval,
    )
    evidence = _read_artifact(layout.artifact_root, "full-evidence-manifest")
    refs = [
        evidence["source_snapshot"],
        evidence["environment"],
        evidence["approval_state"],
        evidence["completed_state"],
        evidence["experiment_spec"],
        evidence["run_manifest"],
        evidence["baseline_fields"],
        evidence["analysis"],
        evidence["validation"],
        *evidence["outputs"].values(),
    ]
    checks = {
        "duplicate_submission": submission.duplicate,
        "backend_not_relaunched": backend.launch_count == 0,
        "provenance_valid": all(_verify_artifact_reference(item) for item in refs),
        "approved_state_reopened": (
            _read_artifact(layout.artifact_root, "full-workflow-approved")["stage"]
            == "FULL_APPROVED_DIAGNOSTIC_REPRODUCTION"
        ),
        "completed_state_reopened": (
            _read_artifact(layout.artifact_root, "full-workflow-completed")["stage"]
            in {"FULL_VALIDATED", "FULL_ROLLED_BACK"}
        ),
    }
    report = {
        "workflow_id": WORKFLOW_ID,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "submission": submission.model_dump(mode="json"),
    }
    if not all(checks.values()):
        raise RuntimeError(f"full replay checks failed: {checks}")
    artifact_store = LocalArtifactStore(layout.artifact_root)
    replay_ref = artifact_store.put_json("full-replay-report", report)
    audit = AppendOnlyAuditStore(layout.audit_database)
    replay_id = "pinn2d-full-replay-verified"
    existing = {record.record_id for record in audit.records_for(WORKFLOW_ID)}
    if replay_id not in existing:
        audit.append(
            record_id=replay_id,
            subject_id=WORKFLOW_ID,
            category="replay_report",
            occurred_at=datetime.now(UTC),
            payload=ModelEvaluationReport(
                report_id="pinn2d-full-replay-evaluation",
                status=ResultStatus.VALID,
                physical_model_authority_ref=ArtifactRef.model_validate(
                    evidence["source_snapshot"]
                ),
                metric_values={"idempotent_relaunch_count": 0.0},
                metric_bases={
                    "idempotent_relaunch_count": MetricEvidenceBasis.BASELINE_RUN
                },
                diagnostic_refs=(replay_ref,),
                checks=checks,
            ),
        )
    print(json.dumps({"replay_report": replay_ref.uri, "status": "PASS"}))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--case-root", type=Path, required=True)
    execute_parser.add_argument("--training-python", type=Path, required=True)
    execute_parser.add_argument("--output-root", type=Path, required=True)
    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "execute":
        execute(
            case_root=args.case_root,
            training_python=args.training_python,
            output_root=args.output_root,
        )
    else:
        replay(output_root=args.output_root)


if __name__ == "__main__":
    main()

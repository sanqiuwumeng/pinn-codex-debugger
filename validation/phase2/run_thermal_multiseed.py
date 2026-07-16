"""Qualify the accepted thermal focused-collocation intervention across seeds.

Seed 42 is an immutable prior governed run.  Additional seeds stage the source
case read-only, change only the random seed, and execute through the production
local backend.  Every result is retained, including metric-gate rejections.
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
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

from pinn_strategy_system.assurance import RunValidationService  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactRef,
    AuditStatus,
    DecisionRecord,
    DecisionStatus,
    MetricEvidenceBasis,
    ModelEvaluationReport,
    PhysicalAuditReport,
    ResultStatus,
    RunManifest,
    RunValidationInput,
)
from pinn_strategy_system.execution import (  # noqa: E402
    ManifestFirstRunner,
    SQLiteRunRegistry,
)
from pinn_strategy_system.storage import AppendOnlyAuditStore  # noqa: E402
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
)

FROZEN_SEEDS = (7, 42, 2026)
BASELINE_TAG = "baseline_uniform_full_immutable"
PRIOR_SEED42_ROOT = (
    REPOSITORY_ROOT
    / "validation"
    / "full"
    / "results"
    / "pinn2d-focused-full-repro-20260716"
)


def _write_json(path: Path, payload: Any) -> ArtifactRef:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {path}")
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return _artifact(path.stem, path)


def _patch_staged_seed(config_path: Path, seed: int) -> ArtifactRef:
    backup = config_path.with_name("config.py_backup_2026-07-16")
    shutil.copy2(config_path, backup)
    source = config_path.read_text(encoding="utf-8")
    old = "    seed: int = 42\n"
    new = f"    seed: int = {seed}\n"
    if source.count(old) != 1:
        raise RuntimeError("staged config does not contain the frozen seed declaration")
    config_path.write_text(source.replace(old, new), encoding="utf-8", newline="\n")
    return _artifact(f"thermal-seed-{seed}-config", config_path)


def _approval(seed: int, approval_ref: ArtifactRef) -> ApprovalRecord:
    return ApprovalRecord(
        approval_id=f"thermal-multiseed-{seed}-approval-20260716",
        workflow_id=f"thermal-multiseed-{seed}-20260716",
        kind=ApprovalKind.EXPERIMENT,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=datetime(2026, 7, 16, tzinfo=UTC),
        scope=(
            "standing authorization for full scientific qualification; only the "
            f"frozen random seed changes for seed {seed}"
        ),
        evidence_refs=(approval_ref,),
    )


def _approval_source() -> Path:
    return (
        REPOSITORY_ROOT
        / "openspec"
        / "changes"
        / "build-rag-multi-agent-dl-strategy-system"
        / "approval-records"
        / "2026-07-16-standing-full-run-authorization.md"
    )


def _manifest(
    *, seed: int, workspace: Path, training_python: Path, config_ref: ArtifactRef
) -> RunManifest:
    run_id = f"thermal-focused-seed-{seed}-20260716"
    output_tag = f"candidate_focused_full_seed_{seed}"
    return RunManifest(
        run_id=run_id,
        workflow_id=f"thermal-multiseed-{seed}-20260716",
        experiment_id=f"thermal-focused-frozen-seed-{seed}-20260716",
        idempotency_key=f"thermal-focused-full-3000-seed-{seed}-20260716",
        environment_name="pinn_full_repro_20260716",
        interpreter=str(training_python),
        working_directory=str(workspace),
        command=(
            str(training_python),
            str(workspace / "run_benchmark.py"),
            "--mode",
            "full",
            "--output-tag",
            output_tag,
        ),
        config_ref=config_ref,
        output_root=str(workspace / "outputs" / output_tag),
        expected_artifacts=EXPECTED_OUTPUTS,
        checkpoint_policy="Persist the full checkpoint and reproducibility manifest.",
        rollback_plan="Retain the common uniform baseline and preserve rejected seed evidence.",
    )


def execute_seed(
    *, seed: int, case_root: Path, training_python: Path, output_root: Path
) -> None:
    if seed not in FROZEN_SEEDS or seed == 42:
        raise ValueError("execute-seed accepts only additional frozen seeds 7 or 2026")
    case_root = case_root.resolve(strict=True)
    training_python = training_python.resolve(strict=True)
    output_root = output_root.resolve(strict=False)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite seed evidence: {output_root}")
    output_root.mkdir(parents=True)

    source_before = _source_snapshot(case_root)
    workspace = output_root / "workspace"
    _stage_case(case_root, workspace, case_root / "pinn_model.py")
    config_ref = _patch_staged_seed(workspace / "config.py", seed)
    baseline_copy = workspace / "outputs" / BASELINE_TAG
    baseline_copy.parent.mkdir()
    shutil.copytree(case_root / "outputs" / "full", baseline_copy)

    environment = _environment_manifest(training_python)
    required_versions = (
        environment["python"] == "3.11.11"
        and environment["torch"].startswith("2.3.1")
        and environment["numpy"] == "2.2.5"
    )
    if not required_versions:
        raise RuntimeError("thermal multiseed requires the exact full-repro environment")

    evidence_root = output_root / "evidence"
    source_ref = _write_json(
        evidence_root / "source-snapshot.json",
        {
            "source_case": str(case_root),
            "source_hashes": source_before,
            "staged_model_sha256": _sha256(workspace / "pinn_model.py"),
            "changed_reproducibility_factor": {"random_seed": seed},
            "scientific_intervention": "12.5 percent focused collocation",
        },
    )
    environment_ref = _write_json(
        evidence_root / "environment.json", environment
    )
    approval_ref = _artifact("standing-full-run-approval", _approval_source())
    approval = _approval(seed, approval_ref)
    _write_json(
        evidence_root / "approval.json", approval.model_dump(mode="json")
    )
    manifest = _manifest(
        seed=seed,
        workspace=workspace,
        training_python=training_python,
        config_ref=config_ref,
    )
    manifest_ref = _write_json(
        evidence_root / "run-manifest.json", manifest.model_dump(mode="json")
    )

    backend_root = output_root / "backend-runs"
    backend_root.mkdir()
    collection_parent = output_root / "collected-runs"
    collection_parent.mkdir()
    collection_root = collection_parent / manifest.run_id
    registry = SQLiteRunRegistry(output_root / "launch-registry.sqlite3")
    audit = AppendOnlyAuditStore(output_root / "audit.sqlite3")
    runner = ManifestFirstRunner(registry, _build_local_backend(backend_root))
    output_directory = Path(manifest.output_root)
    completed = _run_one(
        manifest=manifest,
        approval=approval,
        runner=runner,
        audit=audit,
        output_directory=output_directory,
        collection_directory=collection_root,
    )
    if completed.exit_code != 0:
        raise RuntimeError(f"thermal seed {seed} process failed; evidence retained")

    analysis = run_case(
        case_root=workspace,
        baseline_name=BASELINE_TAG,
        candidate_name=output_directory.name,
    )
    analysis_ref = _write_json(evidence_root / "analysis.json", analysis)
    decision_status = DecisionStatus(analysis["metric_gate"]["status"])
    decision = DecisionRecord(
        decision_id=f"thermal-seed-{seed}-metric-decision",
        status=decision_status,
        observed_failure_mechanism=(
            "localized reference-backed thermal field error against the common "
            "immutable numerical test reference"
        ),
        selected_intervention=(
            "12.5 percent focused collocation"
            if decision_status is DecisionStatus.ACCEPT
            else None
        ),
        unchanged_controls=(
            "physical model and unit system",
            "network architecture",
            "optimizer and learning rate",
            "3000 epochs and 20000 collocation points",
            "FEM discretization and reference",
        ),
        supporting_evidence_refs=(analysis_ref,),
        expected_primary_metric_movement={"max_abs": "decrease", "rmse": "tie-break"},
        guardrail_limits={
            "mae_absolute_regression_K": 1.0,
            "mae_relative_regression": 0.10,
        },
        falsification_condition="Reject this seed when metric or provenance gates fail.",
        rollback_plan="Keep the common immutable uniform baseline active.",
        reasons=tuple(analysis["metric_gate"]["reasons"]),
    )
    candidate_metrics = analysis["prediction_analysis"]["candidate_global_metrics"]
    physical = PhysicalAuditReport(
        report_id=f"thermal-seed-{seed}-physical-audit",
        unit_system_id="pinn-2d-test-case-si",
        status=AuditStatus(analysis["physical_audit"]["status"]),
        source_files_unchanged=analysis["physical_audit"]["source_files_unchanged"],
    )
    evaluation = ModelEvaluationReport(
        report_id=f"thermal-seed-{seed}-evaluation",
        status=ResultStatus(analysis["prediction_analysis"]["status"]),
        physical_model_authority_ref=_artifact(
            "thermal-physical-model-authority", workspace / "physics.py"
        ),
        metric_values={name: float(value) for name, value in candidate_metrics.items()},
        metric_bases={
            name: MetricEvidenceBasis.REFERENCE_EVIDENCE for name in candidate_metrics
        },
        prediction_analysis_ref=analysis_ref,
        diagnostic_refs=(completed.artifacts["data/aligned_fields.npz"],),
        domain_provider_ids=("heat-transfer.phase-change.v1",),
        checks={
            "physical_audit": physical.status is AuditStatus.PASS,
            "field_alignment": analysis["prediction_analysis"]["status"] == "RESULT_VALID",
            "source_integrity": analysis["read_only"]["all_observed_sources_unchanged"],
        },
    )
    baseline_ref = _artifact(
        "common-uniform-baseline-fields",
        baseline_copy / "data" / "aligned_fields.npz",
    )
    validation = RunValidationService().validate(
        report_id=f"thermal-seed-{seed}-validation",
        validation_input=RunValidationInput(
            run_id=manifest.run_id,
            process_exit_code=completed.exit_code,
            physical_audit=physical,
            model_evaluation=evaluation,
            metric_decision=decision,
            required_artifacts=EXPECTED_OUTPUTS,
            produced_artifacts=completed.artifacts,
            run_manifest_ref=manifest_ref,
            source_snapshot_ref=source_ref,
            dataset_refs=(baseline_ref,),
            environment_ref=environment_ref,
            random_seed=seed,
        ),
    )
    validation_ref = _write_json(
        evidence_root / "validation.json", validation.model_dump(mode="json")
    )

    replay_backend = ForbiddenReplayBackend()
    replay = ManifestFirstRunner(
        SQLiteRunRegistry(output_root / "launch-registry.sqlite3"), replay_backend
    ).submit(manifest, approval)
    replay_checks = {
        "duplicate_submission": replay.duplicate,
        "backend_not_relaunched": replay_backend.launch_count == 0,
        "manifest_sha256": bool(manifest_ref.sha256),
        "source_case_unchanged": source_before == _source_snapshot(case_root),
    }
    report = {
        "case": "thermal focused-collocation qualification",
        "seed": seed,
        "common_baseline_boundary": (
            "All focused seeds are compared with the immutable uniform seed-42 "
            "baseline; this is not a paired uniform-baseline seed study."
        ),
        "environment": environment,
        "process": {
            "exit_code": completed.exit_code,
            "submission": completed.submission,
            "monitoring": completed.monitoring,
        },
        "analysis": analysis["prediction_analysis"],
        "decision": decision.model_dump(mode="json"),
        "validation": validation.model_dump(mode="json"),
        "replay": {
            "status": "PASS" if all(replay_checks.values()) else "FAIL",
            "checks": replay_checks,
        },
        "provenance": {
            "source_snapshot_ref": source_ref.model_dump(mode="json"),
            "environment_ref": environment_ref.model_dump(mode="json"),
            "manifest_ref": manifest_ref.model_dump(mode="json"),
            "analysis_ref": analysis_ref.model_dump(mode="json"),
            "validation_ref": validation_ref.model_dump(mode="json"),
            "baseline_ref": baseline_ref.model_dump(mode="json"),
        },
    }
    _write_json(output_root / "seed-execution-report.json", report)
    print(
        json.dumps(
            {
                "seed": seed,
                "decision": decision_status.value,
                "validation": validation.status.value,
                "replay": report["replay"]["status"],
                "report": str(output_root / "seed-execution-report.json"),
            }
        )
    )


def _prior_seed42() -> dict[str, Any]:
    report_path = PRIOR_SEED42_ROOT / "full-execution-report.json"
    replay_path = (
        PRIOR_SEED42_ROOT / "runtime" / "artifacts" / "full-replay-report.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    return {
        "seed": 42,
        "decision": report["metric_decision"]["status"],
        "validation": report["validation"]["status"],
        "replay": replay["status"],
        "analysis": report["localized_analysis"],
        "report_ref": _artifact("thermal-seed-42-report", report_path).model_dump(
            mode="json"
        ),
    }


def aggregate(
    *, seed_7_report: Path, seed_2026_report: Path, output: Path
) -> None:
    output = output.resolve(strict=False)
    entries = [_prior_seed42()]
    for seed, supplied_path in (
        (7, seed_7_report),
        (2026, seed_2026_report),
    ):
        report_path = supplied_path.resolve(strict=True)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["seed"] != seed:
            raise ValueError(f"report does not belong to frozen seed {seed}")
        if report["replay"]["status"] != "PASS":
            raise ValueError(f"seed {seed} report failed replay qualification")
        entries.append(
            {
                "seed": seed,
                "decision": report["decision"]["status"],
                "validation": report["validation"]["status"],
                "replay": report["replay"]["status"],
                "analysis": report["analysis"],
                "report_ref": _artifact(
                    f"thermal-seed-{seed}-report", report_path
                ).model_dump(mode="json"),
            }
        )
    entries.sort(key=lambda item: item["seed"])

    metric_names = ("max_abs", "rmse", "mae")
    aggregate_metrics = {}
    for name in metric_names:
        values = [
            float(item["analysis"]["candidate_global_metrics"][name])
            for item in entries
        ]
        aggregate_metrics[name] = {
            "mean": statistics.fmean(values),
            "sample_std": statistics.stdev(values),
            "min": min(values),
            "max": max(values),
        }
    payload = {
        "frozen_seeds": list(FROZEN_SEEDS),
        "selection_policy": "predeclared fixed seeds; no result-based omission",
        "metric_policy": {
            "primary_order": ["max_abs", "rmse"],
            "aggregation": "LEXICOGRAPHIC",
            "mae_guardrail": {
                "absolute_regression_limit_K": 1.0,
                "relative_regression_limit": 0.10,
                "both_limits_required": True,
            },
        },
        "common_baseline_boundary": (
            "Each focused candidate uses the same immutable uniform seed-42 "
            "baseline and numerical reference. Results quantify candidate seed "
            "uncertainty, not paired intervention effect uncertainty."
        ),
        "per_seed": entries,
        "aggregate_candidate_uncertainty": aggregate_metrics,
        "accept_count": sum(item["decision"] == "ACCEPT" for item in entries),
        "rejected_seeds": [
            item["seed"] for item in entries if item["decision"] != "ACCEPT"
        ],
    }
    _write_json(output, payload)
    print(json.dumps({"report": str(output), "seeds": list(FROZEN_SEEDS)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute = subparsers.add_parser("execute-seed")
    execute.add_argument("--seed", type=int, required=True)
    execute.add_argument("--case-root", type=Path, required=True)
    execute.add_argument("--training-python", type=Path, required=True)
    execute.add_argument("--output-root", type=Path, required=True)
    combine = subparsers.add_parser("aggregate")
    combine.add_argument("--seed-7-report", type=Path, required=True)
    combine.add_argument("--seed-2026-report", type=Path, required=True)
    combine.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "execute-seed":
        execute_seed(
            seed=args.seed,
            case_root=args.case_root,
            training_python=args.training_python,
            output_root=args.output_root,
        )
    else:
        aggregate(
            seed_7_report=args.seed_7_report,
            seed_2026_report=args.seed_2026_report,
            output=args.output,
        )


if __name__ == "__main__":
    main()

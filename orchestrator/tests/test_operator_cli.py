from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.application import OperatorCase  # noqa: E402
from pinn_strategy_system.cli import main  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    AggregationPolicy,
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactRef,
    BudgetSpec,
    ChunkingPolicy,
    ChunkMetadata,
    ExperimentDraft,
    InterventionChange,
    KnowledgeChunk,
    MetricContract,
    MetricDirection,
    MetricEvidenceBasis,
    MetricRole,
    MetricRule,
    ModelEvaluationReport,
    PhysicalModelAuthority,
    ResultStatus,
    RunManifest,
    SourceRef,
    UnitSystemContract,
    WorkflowIntent,
    WorkflowRequest,
)
from pinn_strategy_system.retrieval import (  # noqa: E402
    EvidenceClaim,
    IndexedKnowledgeDocument,
    RetrievalScope,
)


NOW = datetime(2026, 7, 16, tzinfo=UTC)
SHA = "a" * 64


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://cli/{name}",
        sha256=SHA,
    )


def source(name: str) -> SourceRef:
    return SourceRef(
        uri=f"artifact://cli-source/{name}",
        sha256=SHA,
        line_start=1,
        line_end=1,
    )


def approval(workflow_id: str, kind: ApprovalKind) -> ApprovalRecord:
    return ApprovalRecord(
        approval_id=f"approval-{workflow_id}-{kind.value}",
        workflow_id=workflow_id,
        kind=kind,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=NOW,
        scope=f"{workflow_id}:{kind.value}",
    )


def metric_contract() -> MetricContract:
    return MetricContract(
        contract_id="metrics-cli",
        physical_model_authority_ref=artifact("model-authority"),
        reference_evidence_refs=(artifact("reference"),),
        metrics=(
            MetricRule(
                name="l2_error",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
            ),
        ),
        primary_order=("l2_error",),
        aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
    )


def evaluation() -> ModelEvaluationReport:
    return ModelEvaluationReport(
        report_id="evaluation-cli",
        status=ResultStatus.VALID,
        physical_model_authority_ref=artifact("model-authority"),
        metric_values={"l2_error": 0.1},
        metric_bases={
            "l2_error": MetricEvidenceBasis.REFERENCE_EVIDENCE,
        },
        prediction_analysis_ref=artifact("prediction"),
        checks={"aligned": True},
    )


def experiment_draft(project_id: str, *, complete: bool) -> ExperimentDraft:
    if not complete:
        return ExperimentDraft(
            experiment_id="experiment-cli",
            project_id=project_id,
        )
    return ExperimentDraft(
        experiment_id="experiment-cli",
        project_id=project_id,
        observed_failure_mechanism="localized residual hotspot",
        supporting_evidence_refs=(artifact("prediction"),),
        interventions=(
            InterventionChange(
                target="sampling.roi_points",
                before=100,
                after=150,
                rationale="increase only localized collocation density",
            ),
        ),
        unchanged_controls=("network", "optimizer", "loss weights"),
        expected_primary_metric_movement={"l2_error": "decrease"},
        guardrail_limits={"conservation_error": 0.01},
        smoke_budget=BudgetSpec(max_steps=10),
        full_budget=BudgetSpec(max_steps=100),
        falsification_condition="Primary error does not improve.",
        rollback_plan="Preserve baseline and reject the candidate.",
        source_snapshot_ref=artifact("snapshot"),
        dataset_refs=(artifact("dataset"),),
        environment_ref=artifact("environment"),
        random_seed=42,
        baseline_run_ref=artifact("baseline"),
        metric_contract_ref=artifact("metrics"),
        output_root="artifact://cli/experiment",
        checkpoint_policy="write declared milestones",
        expected_artifacts=("metrics.json",),
    )


def operator_case(
    *,
    workflow_id: str,
    intent: WorkflowIntent,
    unit_confirmed: bool = True,
    complete_experiment: bool = True,
    approvals: tuple[ApprovalRecord, ...] | None = None,
    smoke_status: ResultStatus = ResultStatus.NOT_EVALUATED,
    manifest: RunManifest | None = None,
    profile_path: Path | None = None,
) -> OperatorCase:
    unit_system = UnitSystemContract(
        unit_system_id="dimensionless-cli",
        name="Dimensionless operator case",
        quantity_units={"u": "dimensionless"},
        source_refs=(source("units"),),
        confirmed_by_user=unit_confirmed,
    )
    model = PhysicalModelAuthority(
        authority_id="authority-cli",
        project_id="project-cli",
        model_family="PINN",
        pde_family="generic-pde",
        task_type="forward",
        governing_equation_refs=(source("equation"),),
        output_channels=("u",),
        unit_system=unit_system,
        confirmed_by_user=True,
    )
    request = WorkflowRequest(
        request_id=f"request-{workflow_id}",
        workflow_id=workflow_id,
        project_id="project-cli",
        objective="Reduce localized PDE error with one governed intervention.",
        intent=intent,
        snapshot_ref=artifact("snapshot"),
        requested_by="user",
    )
    approved = approvals
    if approved is None:
        approved = (
            approval(workflow_id, ApprovalKind.METRIC_PRIORITY),
            approval(workflow_id, ApprovalKind.EXPERIMENT),
        )
    return OperatorCase(
        case_id=f"case-{workflow_id}",
        request=request,
        unit_system=unit_system,
        physical_model=model,
        metric_contract=metric_contract(),
        model_evaluation=evaluation(),
        experiment_draft=experiment_draft(
            "project-cli",
            complete=complete_experiment,
        ),
        approvals=approved,
        smoke_validation_status=smoke_status,
        smoke_manifest=manifest if intent is WorkflowIntent.SMOKE else None,
        full_manifest=manifest if intent is WorkflowIntent.FULL_RUN else None,
        execution_profile_path=profile_path,
    )


def write_case(path: Path, case: OperatorCase) -> None:
    path.write_text(case.model_dump_json(indent=2), encoding="utf-8")


def invoke(*arguments: str) -> tuple[int, dict]:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = main(list(arguments))
    lines = stream.getvalue().splitlines()
    if len(lines) != 1:
        raise AssertionError(f"expected one JSON line, got {lines!r}")
    return code, json.loads(lines[0])


class OperatorCliTests(unittest.TestCase):
    def test_audit_persists_exact_unit_confirmation_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            case_path = root / "case.json"
            case = operator_case(
                workflow_id="workflow-unit",
                intent=WorkflowIntent.READ_ONLY,
                unit_confirmed=False,
            )
            write_case(case_path, case)
            code, payload = invoke(
                "audit",
                "--runtime-root",
                str(runtime),
                "--case",
                str(case_path),
                "--json",
            )
            self.assertEqual(code, 2)
            self.assertEqual(payload["outcome"], "NEEDS_INPUT")
            self.assertEqual(payload["stage"], "NEEDS_UNIT_CONFIRMATION")
            codes = {
                item["code"] for item in payload["data"]["unresolved"]
            }
            self.assertIn("UNIT_SYSTEM_UNCONFIRMED", codes)
            self.assertTrue((runtime / "workflows" / "catalog.sqlite3").is_file())
            self.assertTrue(
                (runtime / "workflows" / "checkpoints.sqlite3").is_file()
            )

    def test_case_revision_resumes_same_workflow_through_application_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            case_path = root / "case.json"
            write_case(
                case_path,
                operator_case(
                    workflow_id="workflow-resume",
                    intent=WorkflowIntent.READ_ONLY,
                    unit_confirmed=False,
                ),
            )
            first, _ = invoke(
                "audit",
                "--runtime-root",
                str(runtime),
                "--case",
                str(case_path),
                "--json",
            )
            self.assertEqual(first, 2)
            write_case(
                case_path,
                operator_case(
                    workflow_id="workflow-resume",
                    intent=WorkflowIntent.READ_ONLY,
                    unit_confirmed=True,
                ),
            )
            second, payload = invoke(
                "audit",
                "--runtime-root",
                str(runtime),
                "--case",
                str(case_path),
                "--json",
            )
            self.assertEqual(second, 0)
            self.assertEqual(payload["stage"], "COMPLETED")

    def test_full_without_persisted_full_approval_never_loads_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            case_path = root / "case.json"
            case = operator_case(
                workflow_id="workflow-full-gate",
                intent=WorkflowIntent.FULL_RUN,
                smoke_status=ResultStatus.VALID,
            )
            write_case(case_path, case)
            audit_code, audit_payload = invoke(
                "audit",
                "--runtime-root",
                str(runtime),
                "--case",
                str(case_path),
                "--json",
            )
            self.assertEqual(audit_code, 2)
            self.assertEqual(
                audit_payload["stage"],
                "NEEDS_FULL_RUN_APPROVAL",
            )
            status_code, status_payload = invoke(
                "status",
                "--runtime-root",
                str(runtime),
                "--workflow",
                "workflow-full-gate",
                "--json",
            )
            self.assertEqual(status_code, 2)
            self.assertEqual(status_payload["outcome"], "NEEDS_INPUT")
            self.assertEqual(
                status_payload["stage"],
                "NEEDS_FULL_RUN_APPROVAL",
            )
            full_code, full_payload = invoke(
                "full",
                "--runtime-root",
                str(runtime),
                "--workflow",
                "workflow-full-gate",
                "--json",
            )
            self.assertEqual(full_code, 2)
            self.assertEqual(
                full_payload["code"],
                "NEEDS_FULL_RUN_APPROVAL",
            )
            self.assertFalse((runtime / "execution" / "runs.sqlite3").exists())

    def test_experiment_approval_cannot_bypass_incomplete_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            case_path = root / "case.json"
            write_case(
                case_path,
                operator_case(
                    workflow_id="workflow-incomplete",
                    intent=WorkflowIntent.SMOKE,
                    complete_experiment=False,
                ),
            )
            code, payload = invoke(
                "plan",
                "--runtime-root",
                str(runtime),
                "--case",
                str(case_path),
                "--json",
            )
            self.assertEqual(code, 2)
            self.assertEqual(payload["stage"], "NEEDS_EXPERIMENT_EVIDENCE")
            self.assertIn(
                "single_intervention",
                payload["data"]["unresolved"]["missing_fields"],
            )

    def test_relative_case_requires_explicit_base_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            write_case(
                root / "case.json",
                operator_case(
                    workflow_id="workflow-relative",
                    intent=WorkflowIntent.READ_ONLY,
                ),
            )
            code, payload = invoke(
                "audit",
                "--runtime-root",
                str(runtime),
                "--case",
                "case.json",
                "--json",
            )
            self.assertEqual(code, 3)
            self.assertEqual(payload["code"], "INPUT_INVALID")
            self.assertNotIn(str(root), json.dumps(payload))

    def test_smoke_status_and_replay_use_one_durable_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            work = root / "work"
            runs = root / "runs"
            output = root / "output"
            work.mkdir()
            runs.mkdir()
            fixture = work / "fixture.py"
            fixture.write_text(
                "\n".join(
                    (
                        "import json, sys, time",
                        "from pathlib import Path",
                        "root = Path(sys.argv[1])",
                        "root.mkdir(parents=True, exist_ok=True)",
                        "time.sleep(0.2)",
                        "(root / 'metrics.json').write_text(json.dumps({'value': 1.0}), encoding='utf-8')",
                    )
                ),
                encoding="utf-8",
            )
            environment_file = root / "environment.json"
            environment = {
                name: os.environ[name]
                for name in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP")
                if name in os.environ
            }
            environment["PYTHONUTF8"] = "1"
            environment_file.write_text(
                json.dumps(environment),
                encoding="utf-8",
            )
            profile_path = root / "execution-profile.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "backend": "local-process",
                        "run_root": str(runs),
                        "launcher_interpreter": sys.executable,
                        "environment_file": str(environment_file),
                        "environment_allowlist": list(environment),
                    }
                ),
                encoding="utf-8",
            )
            manifest = RunManifest(
                run_id="run-cli-smoke",
                workflow_id="workflow-smoke",
                experiment_id="experiment-cli",
                idempotency_key="idem-cli-smoke",
                environment_name="pinn_strategy_orchestrator",
                interpreter=sys.executable,
                working_directory=str(work),
                command=(sys.executable, str(fixture), str(output)),
                config_ref=artifact("smoke-config"),
                output_root=str(output),
                expected_artifacts=("metrics.json",),
                checkpoint_policy="single bounded fixture",
                rollback_plan="preserve fixture evidence",
            )
            case_path = root / "case.json"
            write_case(
                case_path,
                operator_case(
                    workflow_id="workflow-smoke",
                    intent=WorkflowIntent.SMOKE,
                    manifest=manifest,
                    profile_path=profile_path,
                ),
            )
            audit_code, audit_payload = invoke(
                "audit",
                "--runtime-root",
                str(runtime),
                "--case",
                str(case_path),
                "--json",
            )
            self.assertEqual(audit_code, 0)
            self.assertEqual(audit_payload["stage"], "SMOKE_APPROVED")
            smoke_code, smoke_payload = invoke(
                "smoke",
                "--runtime-root",
                str(runtime),
                "--workflow",
                "workflow-smoke",
                "--json",
            )
            self.assertEqual(smoke_code, 0)
            self.assertEqual(smoke_payload["code"], "RUNNING")
            deadline = time.time() + 10
            status_payload = None
            while time.time() < deadline:
                _, status_payload = invoke(
                    "status",
                    "--runtime-root",
                    str(runtime),
                    "--workflow",
                    "workflow-smoke",
                    "--json",
                )
                if status_payload["code"] == "COMPLETED":
                    break
                time.sleep(0.05)
            self.assertIsNotNone(status_payload)
            self.assertEqual(status_payload["code"], "COMPLETED")
            replay_code, replay_payload = invoke(
                "replay",
                "--runtime-root",
                str(runtime),
                "--workflow",
                "workflow-smoke",
                "--json",
            )
            self.assertEqual(replay_code, 0)
            self.assertEqual(replay_payload["code"], "COMPLETED")
            self.assertTrue(replay_payload["data"]["zero_relaunch_replay"])
            launcher_files = tuple(runs.rglob("launcher-identity.json"))
            self.assertEqual(len(launcher_files), 1)

    def test_rag_rebuild_and_query_expose_active_provenance_and_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            knowledge = root / "knowledge"
            knowledge.mkdir()
            handbook = knowledge / "handbook.md"
            texts = (
                "radiation boundary requires absolute temperature in kelvin",
                "legacy radiation note consumes degrees Celsius directly",
                *(f"generic PINN evidence document {index}" for index in range(8)),
            )
            handbook.write_text("\n".join(texts), encoding="utf-8")
            source_sha = hashlib.sha256(handbook.read_bytes()).hexdigest()
            for index, text in enumerate(texts):
                claims = ()
                if index == 0:
                    claims = (
                        EvidenceClaim(
                            key="radiation_temperature_unit",
                            value="K",
                        ),
                    )
                elif index == 1:
                    claims = (
                        EvidenceClaim(
                            key="radiation_temperature_unit",
                            value="degC",
                        ),
                    )
                document = IndexedKnowledgeDocument(
                    chunk=KnowledgeChunk(
                        chunk_id=f"doc-{index:02d}",
                        text=text,
                        chunk_sha256=hashlib.sha256(
                            text.encode("utf-8")
                        ).hexdigest(),
                        metadata=ChunkMetadata(
                            project_id="project-cli",
                            source_ref=SourceRef(
                                uri=handbook.as_uri(),
                                sha256=source_sha,
                                line_start=index + 1,
                                line_end=index + 1,
                            ),
                            repo_commit="abc123",
                            model_family="PINN",
                            pde_family="generic-pde",
                            task_type="forward",
                            document_type="HANDBOOK",
                            validation_status="SOURCE_VERIFIED",
                            valid_from=NOW,
                            language="en",
                        ),
                    ),
                    claims=claims,
                )
                (knowledge / f"doc-{index:02d}.index.json").write_text(
                    document.model_dump_json(indent=2),
                    encoding="utf-8",
                )
            gateway = root / "fake-qwen-gateway.py"
            gateway.write_text(
                "\n".join(
                    (
                        "import json, sys",
                        "role = sys.argv[1]",
                        "embedding_id = 'Qwen/Qwen3-Embedding-8B'",
                        "embedding_revision = '1d8ad4ca9b3dd8059ad90a75d4983776a23d44af'",
                        "reranker_id = 'Qwen/Qwen3-Reranker-4B'",
                        "reranker_revision = '22e683669bc0f0bd69640a1354a6d0aebcfeede5'",
                        "for line in sys.stdin:",
                        "    request = json.loads(line)",
                        "    if role == 'embedding':",
                        "        vectors = []",
                        "        for text in request['texts']:",
                        "            vector = [0.0] * 4096",
                        "            vector[0 if ('radiation' in text.lower() or request['input_type'] == 'query') else 1] = 1.0",
                        "            vectors.append(vector)",
                        "        response = {'schema_version':'1.0','operation':'embed','request_id':request['request_id'],'provenance':{'schema_version':'1.0','model_id':embedding_id,'revision':embedding_revision,'runtime_id':'test-gateway','runtime_version':'1.0','precision':'float32'},'output_dimension':4096,'vectors':vectors}",
                        "    else:",
                        "        scores = [{'schema_version':'1.0','document_id':item['document_id'],'score':float(len(request['documents']) - index)} for index, item in enumerate(request['documents'])]",
                        "        response = {'schema_version':'1.0','operation':'rerank','request_id':request['request_id'],'provenance':{'schema_version':'1.0','model_id':reranker_id,'revision':reranker_revision,'runtime_id':'test-gateway','runtime_version':'1.0','precision':'float32'},'scores':scores}",
                        "    print(json.dumps(response), flush=True)",
                    )
                ),
                encoding="utf-8",
            )
            environment_file = root / "model-environment.json"
            environment = {
                name: os.environ[name]
                for name in ("SYSTEMROOT", "WINDIR", "PATH")
                if name in os.environ
            }
            environment_file.write_text(
                json.dumps(environment),
                encoding="utf-8",
            )
            model_profile = root / "model-profile.json"
            role_profile = lambda role: {
                "schema_version": "1.0",
                "executable": sys.executable,
                "arguments": [str(gateway), role],
                "working_directory": str(root),
                "environment_file": str(environment_file),
                "timeout_seconds": 30,
            }
            model_profile.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "embedding": role_profile("embedding"),
                        "reranker": role_profile("reranker"),
                    }
                ),
                encoding="utf-8",
            )
            case = operator_case(
                workflow_id="workflow-rag",
                intent=WorkflowIntent.READ_ONLY,
            ).model_copy(
                update={
                    "chunking_policy": ChunkingPolicy(
                        policy_id="cli-rag-v1",
                        max_characters=2048,
                        overlap_characters=128,
                        document_types=("HANDBOOK",),
                    ),
                    "retrieval_scope": RetrievalScope(
                        project_id="project-cli",
                        evidence_mode="all",
                    ),
                }
            )
            case_path = root / "case.json"
            write_case(case_path, case)
            rebuild_code, rebuild_payload = invoke(
                "rag",
                "rebuild",
                "--runtime-root",
                str(runtime),
                "--source",
                str(knowledge),
                "--case",
                str(case_path),
                "--model-profile",
                str(model_profile),
                "--json",
            )
            self.assertEqual(rebuild_code, 0)
            self.assertEqual(rebuild_payload["code"], "INDEX_ACTIVATED")
            active = rebuild_payload["data"]["active_index"]["active"]
            self.assertEqual(
                active["embedding_model_id"],
                "Qwen/Qwen3-Embedding-8B",
            )
            query_code, query_payload = invoke(
                "rag",
                "query",
                "--runtime-root",
                str(runtime),
                "--case",
                str(case_path),
                "--model-profile",
                str(model_profile),
                "--query",
                "Which unit must the radiation boundary use?",
                "--json",
            )
            self.assertEqual(query_code, 0)
            self.assertEqual(query_payload["code"], "CONFLICTS_VISIBLE")
            self.assertEqual(query_payload["data"]["candidate_count"], 10)
            self.assertFalse(query_payload["data"]["decision_safe"])
            self.assertEqual(
                query_payload["data"]["conflicts"][0]["claim_key"],
                "radiation_temperature_unit",
            )


if __name__ == "__main__":
    unittest.main()

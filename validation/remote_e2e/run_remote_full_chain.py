"""Run the formal Wiki, Qwen RAG and Poisson PINN chain on one remote host."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
POISSON_ROOT = REPOSITORY_ROOT / "validation" / "phase2" / "poisson"
sys.path.insert(0, str(ORCHESTRATOR_SRC))
sys.path.insert(0, str(POISSON_ROOT))

from pinn_strategy_system.application import (  # noqa: E402
    OperatorCase,
    ProjectAdapterManifest,
)
from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactRef,
    BudgetSpec,
    ChunkMetadata,
    ChunkingPolicy,
    ExperimentDraft,
    InterventionChange,
    KnowledgeChunk,
    MetricEvidenceBasis,
    ModelEvaluationReport,
    ResultStatus,
    SourceRef,
    WorkflowIntent,
    WorkflowRequest,
    WikiPublicationSpec,
)
from pinn_strategy_system.retrieval import (  # noqa: E402
    EvidenceClaim,
    IndexedKnowledgeDocument,
    QWEN3_EMBEDDING_MODEL_ID,
    QWEN3_EMBEDDING_REVISION,
    QWEN3_RERANKER_MODEL_ID,
    QWEN3_RERANKER_REVISION,
    RetrievalScope,
)
from run_poisson_qualification import _case_contracts  # noqa: E402


PUBLISHED_WIKI_CHUNK = "peer-pinn-localized-collocation-v0001"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite remote evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _artifact(artifact_id: str, uri: str, sha256: str) -> ArtifactRef:
    return ArtifactRef(artifact_id=artifact_id, uri=uri, sha256=sha256)


def _run(
    *,
    label: str,
    command: list[str],
    evidence_root: Path,
    cwd: Path,
    timeout: int,
    environment: dict[str, str] | None = None,
    expect_codes: tuple[int, ...] = (0,),
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    payload = {
        "schema_version": "1.0",
        "label": label,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    _write_json(evidence_root / f"{label}.json", payload)
    if completed.returncode not in expect_codes:
        raise RuntimeError(f"{label} failed with exit code {completed.returncode}")
    return payload


def _json_stdout(record: dict[str, Any]) -> dict[str, Any]:
    lines = [line for line in record["stdout"].splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"{record['label']} returned no JSON output")
    payload = json.loads(lines[-1])
    if not isinstance(payload, dict):
        raise RuntimeError(f"{record['label']} JSON output is not an object")
    return payload


def _verify_input_packet(input_root: Path, repo_commit: str) -> dict[str, Any]:
    manifest_path = input_root / "input-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["repo_commit"] != repo_commit:
        raise RuntimeError("input packet commit does not match staged source")
    for item in manifest["files"]:
        path = (input_root / item["relative_path"]).resolve(strict=True)
        path.relative_to(input_root)
        if not path.is_file():
            raise RuntimeError("input manifest references a non-file")
        if path.stat().st_size != item["size_bytes"] or _sha256(path) != item["sha256"]:
            raise RuntimeError("input packet content failed manifest validation")
    return manifest


def _write_environment_files(
    *,
    result_root: Path,
    qwen_python: Path,
    qwen_cache_root: Path,
    embedding_snapshot: Path,
    reranker_snapshot: Path,
) -> tuple[Path, Path]:
    environment_path = result_root / "contracts" / "qwen-environment.json"
    environment = {
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
        "CUDA_VISIBLE_DEVICES": "0",
        "HF_HOME": str(qwen_cache_root.parent),
        "HF_HUB_CACHE": str(qwen_cache_root),
        "HF_HUB_OFFLINE": "1",
        "HOME": os.environ.get("HOME", "/root"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "PATH": os.environ["PATH"],
        "PYTHONHASHSEED": "0",
        "TOKENIZERS_PARALLELISM": "false",
        "TRANSFORMERS_OFFLINE": "1",
    }
    _write_json(environment_path, environment)
    profile_path = result_root / "contracts" / "qwen-model-profile.json"
    gateway = REPOSITORY_ROOT / "retrieval-runtime" / "qwen3_jsonl_gateway.py"

    def role(role_name: str, snapshot: Path, revision: str) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "executable": str(qwen_python),
            "arguments": [
                str(gateway),
                "--role",
                role_name,
                "--snapshot",
                str(snapshot),
                "--revision",
                revision,
                "--max-length",
                "2048",
                "--batch-size",
                "4",
            ],
            "working_directory": str(REPOSITORY_ROOT),
            "environment_file": str(environment_path),
            "timeout_seconds": 600.0,
            "max_request_bytes": 8388608,
            "max_response_bytes": 67108864,
        }

    _write_json(
        profile_path,
        {
            "schema_version": "1.0",
            "embedding": role(
                "embedding",
                embedding_snapshot,
                QWEN3_EMBEDDING_REVISION,
            ),
            "reranker": role(
                "reranker",
                reranker_snapshot,
                QWEN3_RERANKER_REVISION,
            ),
        },
    )
    return environment_path, profile_path


def _build_operator_case(
    *,
    repo_commit: str,
    source_archive_sha256: str,
    publication: WikiPublicationSpec,
) -> OperatorCase:
    worker = POISSON_ROOT / "poisson_pinn_worker.py"
    unit_system, authority, reference, metric_contract = _case_contracts(worker)
    project_id = publication.project_id
    authority = authority.model_copy(update={"project_id": project_id})
    snapshot = _artifact(
        "remote-source-archive",
        "artifact://remote-e2e/source-archive",
        source_archive_sha256,
    )
    evaluation = ModelEvaluationReport(
        report_id="remote-e2e-baseline-evaluation",
        status=ResultStatus.VALID,
        physical_model_authority_ref=metric_contract.physical_model_authority_ref,
        metric_values={
            "relative_l2": 1.0e-3,
            "poisson_pde_residual_rms": 5.0e-2,
            "poisson_boundary_max_abs": 0.0,
            "max_abs": 2.0e-3,
            "poisson_relative_h1": 2.0e-3,
        },
        metric_bases={
            "relative_l2": MetricEvidenceBasis.REFERENCE_EVIDENCE,
            "poisson_pde_residual_rms": MetricEvidenceBasis.PHYSICAL_MODEL,
            "poisson_boundary_max_abs": MetricEvidenceBasis.PHYSICAL_MODEL,
            "max_abs": MetricEvidenceBasis.REFERENCE_EVIDENCE,
            "poisson_relative_h1": MetricEvidenceBasis.REFERENCE_EVIDENCE,
        },
        prediction_analysis_ref=_artifact(
            "remote-e2e-baseline-analysis",
            "artifact://remote-e2e/baseline-analysis",
            "b" * 64,
        ),
        checks={"aligned_reference": True, "localized_maximum": True},
    )
    workflow_id = "remote-e2e-poisson-rag"
    approved_at = publication.published_at
    approvals = tuple(
        ApprovalRecord(
            approval_id=f"remote-e2e-{kind.value.lower()}-approval",
            workflow_id=workflow_id,
            kind=kind,
            decision=ApprovalDecision.APPROVED,
            approved_by="user",
            approved_at=approved_at,
            scope=f"{workflow_id}:{kind.value}",
        )
        for kind in (ApprovalKind.METRIC_PRIORITY, ApprovalKind.EXPERIMENT)
    )
    experiment = ExperimentDraft(
        experiment_id="remote-e2e-poisson-experiment",
        project_id=project_id,
        observed_failure_mechanism="localized maximum reference error",
        supporting_evidence_refs=(evaluation.prediction_analysis_ref,),
        interventions=(
            InterventionChange(
                target="collocation.focus_fraction",
                before=0.0,
                after=0.125,
                rationale="replace one eighth of uniform points near baseline max_abs",
            ),
        ),
        unchanged_controls=(
            "physics",
            "network",
            "optimizer",
            "seed",
            "epoch budget",
            "total collocation count",
        ),
        expected_primary_metric_movement={"relative_l2": "decrease"},
        guardrail_limits={"poisson_boundary_max_abs": 1.0e-6},
        smoke_budget=BudgetSpec(max_steps=20),
        full_budget=BudgetSpec(max_steps=1800),
        falsification_condition="relative_l2 does not improve or boundary gate fails",
        rollback_plan="retain the uniform baseline",
        source_snapshot_ref=snapshot,
        dataset_refs=(reference.artifact_ref,),
        environment_ref=_artifact(
            "remote-pinn-environment",
            "artifact://remote-e2e/pinn-environment",
            "c" * 64,
        ),
        random_seed=314159,
        baseline_run_ref=_artifact(
            "remote-poisson-baseline",
            "artifact://remote-e2e/poisson-baseline",
            "d" * 64,
        ),
        metric_contract_ref=metric_contract.physical_model_authority_ref,
        output_root="artifact://remote-e2e/poisson-output",
        checkpoint_policy="persist declared fields, metrics and hashes",
        expected_artifacts=("aligned_fields.json", "model_state.pt"),
    )
    return OperatorCase(
        case_id="remote-e2e-poisson-case",
        request=WorkflowRequest(
            request_id="remote-e2e-poisson-request",
            workflow_id=workflow_id,
            project_id=project_id,
            objective=(
                "Determine whether localized collocation is a universal PINN rule "
                "or a case-scoped intervention requiring measured validation."
            ),
            intent=WorkflowIntent.READ_ONLY,
            snapshot_ref=snapshot,
            requested_by="user",
        ),
        unit_system=unit_system,
        physical_model=authority,
        references=(reference,),
        metric_contract=metric_contract,
        model_evaluation=evaluation,
        experiment_draft=experiment,
        approvals=approvals,
        chunking_policy=ChunkingPolicy(
            policy_id="remote-e2e-rag-v1",
            max_characters=4096,
            overlap_characters=128,
            document_types=("HANDBOOK", "WIKI"),
        ),
        retrieval_scope=RetrievalScope(
            project_id=project_id,
            document_types=("HANDBOOK", "WIKI"),
            validation_statuses=("SOURCE_VERIFIED", "APPROVED"),
            model_family="PINN",
            evidence_mode="all",
        ),
    )


def _write_fixture_documents(
    *,
    knowledge_root: Path,
    project_id: str,
    repo_commit: str,
    valid_from: datetime,
) -> None:
    packet_path = (
        REPOSITORY_ROOT
        / "validation"
        / "benchmarks"
        / "qwen3_retrieval_benchmark_cases_v1.json"
    )
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet_sha = _sha256(packet_path)
    fixture_root = knowledge_root / "frozen-corpus"
    if fixture_root.exists():
        raise FileExistsError("frozen Wiki corpus output already exists")
    fixture_root.mkdir(parents=True)
    for item in packet["corpus"]:
        text = f"{item['title']}\n{item['text']}"
        document = IndexedKnowledgeDocument(
            chunk=KnowledgeChunk(
                chunk_id=item["id"],
                text=text,
                chunk_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                metadata=ChunkMetadata(
                    project_id=project_id,
                    source_ref=SourceRef(
                        uri=packet_path.as_uri(),
                        sha256=packet_sha,
                    ),
                    artifact_range=f"corpus[id={item['id']}]",
                    repo_commit=repo_commit,
                    model_family="PINN",
                    task_type="strategy-optimization",
                    document_type="HANDBOOK",
                    validation_status="SOURCE_VERIFIED",
                    valid_from=valid_from,
                    language="en",
                ),
            ),
            applicable_versions=(repo_commit,),
            claims=tuple(
                EvidenceClaim(key=claim["key"], value=claim["value"])
                for claim in item["claims"]
            ),
        )
        _write_json(
            fixture_root / f"{item['id']}.index.json",
            document.model_dump(mode="json"),
        )


def _cli(*arguments: str) -> list[str]:
    return [sys.executable, "-m", "pinn_strategy_system.cli", *arguments]


def _assert_rag_results(
    *,
    query_payload: dict[str, Any],
    conflict_payload: dict[str, Any],
) -> None:
    if query_payload.get("outcome") != "SUCCESS":
        raise RuntimeError("advisory RAG query did not succeed")
    evidence = query_payload["data"]["evidence"]
    by_id = {item["evidence_id"]: item for item in evidence}
    if PUBLISHED_WIKI_CHUNK not in by_id:
        raise RuntimeError("published Wiki was absent after Qwen reranking")
    wiki = by_id[PUBLISHED_WIKI_CHUNK]
    if wiki["reranker_model_id"] != QWEN3_RERANKER_MODEL_ID:
        raise RuntimeError("published Wiki reranker model identity mismatch")
    if wiki["reranker_model_revision"] != QWEN3_RERANKER_REVISION:
        raise RuntimeError("published Wiki reranker revision mismatch")
    active = query_payload["data"]["active_index"]
    if active["active"]["embedding_model_id"] != QWEN3_EMBEDDING_MODEL_ID:
        raise RuntimeError("active index embedding model identity mismatch")
    if active["active"]["embedding_revision"] != QWEN3_EMBEDDING_REVISION:
        raise RuntimeError("active index embedding revision mismatch")
    conflicts = {
        item["claim_key"] for item in conflict_payload["data"]["conflicts"]
    }
    if "radiation_temperature_unit" not in conflicts:
        raise RuntimeError("known conflict was not visible to the operator")
    if conflict_payload["data"]["decision_safe"]:
        raise RuntimeError("conflicting evidence was incorrectly decision-safe")


def _scan_result_credentials(result_root: Path) -> None:
    patterns = (
        re.compile(r"-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----"),
        re.compile(r"\bssh\s+-p\s+\d+\s+[A-Za-z0-9_.-]+@"),
        re.compile(
            r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token)\b"
            r"\s*[:=]\s*['\"][^'\"]{4,}['\"]"
        ),
    )
    for path in result_root.rglob("*"):
        if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in patterns):
            raise RuntimeError("credential marker detected in remote result evidence")


def execute(args: argparse.Namespace) -> None:
    project_root = args.project_root.resolve(strict=True)
    input_root = args.input_root.resolve(strict=True)
    source_archive = args.source_archive.resolve(strict=True)
    qwen_python = args.qwen_python.resolve(strict=True)
    pinn_python = args.pinn_python.resolve(strict=True)
    qwen_cache_root = args.qwen_cache_root.resolve(strict=True)
    result_root = args.result_root.resolve(strict=False)
    if result_root.exists():
        raise FileExistsError("remote full-chain result root already exists")
    if _sha256(source_archive) != args.source_archive_sha256:
        raise RuntimeError("staged source archive hash mismatch")
    _verify_input_packet(input_root, args.repo_commit)
    result_root.mkdir(parents=True)
    evidence_root = result_root / "steps"
    knowledge_root = result_root / "knowledge"
    runtime_root = result_root / "runtime"
    evidence_root.mkdir()
    knowledge_root.mkdir()
    runtime_root.mkdir()
    started_at = datetime.now(UTC)
    _write_json(
        result_root / "run-start.json",
        {
            "schema_version": "1.0",
            "started_at": started_at.isoformat(),
            "repo_commit": args.repo_commit,
            "source_archive_sha256": args.source_archive_sha256,
            "seed": args.seed,
        },
    )

    qwen_smoke = _run(
        label="01-qwen-gpu-smoke",
        command=[
            str(qwen_python),
            "-c",
            (
                "import json,torch; "
                "x=torch.ones((1024,1024),device='cuda'); "
                "y=(x@x).sum(); torch.cuda.synchronize(); "
                "print(json.dumps({'torch':torch.__version__,'gpu':torch.cuda.get_device_name(0),'sum':float(y)}))"
            ),
        ],
        evidence_root=evidence_root,
        cwd=project_root,
        timeout=120,
    )
    _json_stdout(qwen_smoke)
    _run(
        label="02-environment-checks",
        command=[
            sys.executable,
            "-c",
            (
                "import importlib.metadata,json,sys,pydantic; "
                "print(json.dumps({'python':sys.version.split()[0],"
                "'pydantic':pydantic.__version__,'qdrant_client':"
                "importlib.metadata.version('qdrant-client')}))"
            ),
        ],
        evidence_root=evidence_root,
        cwd=project_root,
        timeout=60,
    )
    _run(
        label="03-pinn-environment",
        command=[
            str(pinn_python),
            "-c",
            (
                "import json,sys,torch,numpy; "
                "print(json.dumps({'python':sys.version.split()[0],"
                "'torch':torch.__version__,'numpy':numpy.__version__,"
                "'cuda_available':torch.cuda.is_available()}))"
            ),
        ],
        evidence_root=evidence_root,
        cwd=project_root,
        timeout=60,
    )

    publication = WikiPublicationSpec.model_validate_json(
        (input_root / "publication.json").read_text(encoding="utf-8")
    )
    case = _build_operator_case(
        repo_commit=args.repo_commit,
        source_archive_sha256=args.source_archive_sha256,
        publication=publication,
    )
    case_path = result_root / "contracts" / "rag-case-template.json"
    _write_json(case_path, case.model_dump(mode="json"))

    mcp_environment_path = result_root / "contracts" / "mcp-environment.json"
    _write_json(
        mcp_environment_path,
        {
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ["PATH"],
            "PYTHONPATH": os.pathsep.join(
                (str(project_root / "mcp-server"), str(ORCHESTRATOR_SRC))
            ),
            "PYTHONUTF8": "1",
        },
    )
    mcp_profile_path = result_root / "contracts" / "mcp-profile.json"
    _write_json(
        mcp_profile_path,
        {
            "schema_version": "1.0",
            "executable": sys.executable,
            "arguments": ["-m", "pinn_hybrid_rag"],
            "working_directory": str(project_root / "mcp-server"),
            "environment_file": str(mcp_environment_path),
            "source_uri": (project_root / "PINN报错诊断与模块选择手册.md").as_uri(),
            "request_timeout_seconds": 30.0,
        },
    )
    diagnose = _run(
        label="04-mcp-diagnose",
        command=_cli(
            "diagnose",
            "--runtime-root",
            str(runtime_root),
            "--project-id",
            publication.project_id,
            "--query",
            "Poisson PINN has a localized maximum error; what evidence is needed before optimization?",
            "--mcp-profile",
            str(mcp_profile_path),
            "--json",
        ),
        evidence_root=evidence_root,
        cwd=project_root,
        timeout=120,
    )
    if _json_stdout(diagnose)["code"] != "MCP_EVIDENCE_READY":
        raise RuntimeError("MCP diagnosis did not return governed evidence")

    adapter_manifest = ProjectAdapterManifest(
        adapter_id="remote-e2e-poisson-adapter",
        project_root=project_root,
        include_files=(
            Path("validation/phase2/poisson/poisson_pinn_worker.py"),
            Path("validation/phase2/poisson/run_poisson_qualification.py"),
        ),
        case_template=case,
    )
    adapter_manifest_path = result_root / "contracts" / "adapter-manifest.json"
    adapted_case_path = result_root / "contracts" / "adapted-case.json"
    _write_json(adapter_manifest_path, adapter_manifest.model_dump(mode="json"))
    adapt = _run(
        label="05-project-adapt",
        command=_cli(
            "adapt",
            "--runtime-root",
            str(runtime_root),
            "--manifest",
            str(adapter_manifest_path),
            "--output",
            str(adapted_case_path),
            "--json",
        ),
        evidence_root=evidence_root,
        cwd=project_root,
        timeout=120,
    )
    if _json_stdout(adapt)["outcome"] != "SUCCESS":
        raise RuntimeError("project adapter left an unexpected unresolved contract")
    for sequence, operation in enumerate(("audit", "plan"), start=6):
        record = _run(
            label=f"{sequence:02d}-{operation}",
            command=_cli(
                operation,
                "--runtime-root",
                str(runtime_root),
                "--case",
                str(adapted_case_path),
                "--json",
            ),
            evidence_root=evidence_root,
            cwd=project_root,
            timeout=120,
        )
        if _json_stdout(record)["outcome"] != "SUCCESS":
            raise RuntimeError(f"operator {operation} did not complete")

    publish = _run(
        label="08-wiki-publish",
        command=_cli(
            "wiki",
            "publish",
            "--runtime-root",
            str(runtime_root),
            "--candidate",
            str(input_root / "candidate.json"),
            "--approval",
            str(input_root / "approval.json"),
            "--publication",
            str(input_root / "publication.json"),
            "--knowledge-root",
            str(knowledge_root),
            "--json",
        ),
        evidence_root=evidence_root,
        cwd=project_root,
        timeout=120,
    )
    if _json_stdout(publish)["code"] != "WIKI_PUBLISHED":
        raise RuntimeError("formal Wiki was not newly published")
    replay_publish = _run(
        label="09-wiki-idempotent-replay",
        command=_cli(
            "wiki",
            "publish",
            "--runtime-root",
            str(runtime_root),
            "--candidate",
            str(input_root / "candidate.json"),
            "--approval",
            str(input_root / "approval.json"),
            "--publication",
            str(input_root / "publication.json"),
            "--knowledge-root",
            str(knowledge_root),
            "--json",
        ),
        evidence_root=evidence_root,
        cwd=project_root,
        timeout=120,
    )
    if _json_stdout(replay_publish)["code"] != "WIKI_VERIFIED":
        raise RuntimeError("formal Wiki idempotent replay failed")

    _write_fixture_documents(
        knowledge_root=knowledge_root,
        project_id=publication.project_id,
        repo_commit=args.repo_commit,
        valid_from=publication.published_at,
    )
    _, model_profile_path = _write_environment_files(
        result_root=result_root,
        qwen_python=qwen_python,
        qwen_cache_root=qwen_cache_root,
        embedding_snapshot=(
            qwen_cache_root
            / "models--Qwen--Qwen3-Embedding-8B"
            / "snapshots"
            / QWEN3_EMBEDDING_REVISION
        ),
        reranker_snapshot=(
            qwen_cache_root
            / "models--Qwen--Qwen3-Reranker-4B"
            / "snapshots"
            / QWEN3_RERANKER_REVISION
        ),
    )
    rebuild = _run(
        label="10-rag-rebuild",
        command=_cli(
            "rag",
            "rebuild",
            "--runtime-root",
            str(runtime_root),
            "--source",
            str(knowledge_root),
            "--case",
            str(adapted_case_path),
            "--model-profile",
            str(model_profile_path),
            "--json",
        ),
        evidence_root=evidence_root,
        cwd=project_root,
        timeout=1200,
    )
    if _json_stdout(rebuild)["code"] != "INDEX_ACTIVATED":
        raise RuntimeError("Qwen-backed RAG index was not activated")
    advisory = _run(
        label="11-rag-advisory-query",
        command=_cli(
            "rag",
            "query",
            "--runtime-root",
            str(runtime_root),
            "--case",
            str(adapted_case_path),
            "--model-profile",
            str(model_profile_path),
            "--query",
            (
                "For an independent Poisson PINN, should max_abs be localized "
                "before focused collocation, and is that intervention universally reliable?"
            ),
            "--json",
        ),
        evidence_root=evidence_root,
        cwd=project_root,
        timeout=1200,
    )
    conflict = _run(
        label="12-rag-conflict-query",
        command=_cli(
            "rag",
            "query",
            "--runtime-root",
            str(runtime_root),
            "--case",
            str(adapted_case_path),
            "--model-profile",
            str(model_profile_path),
            "--query",
            "Should a radiation boundary use kelvin or degrees Celsius directly? Return conflicting evidence.",
            "--json",
        ),
        evidence_root=evidence_root,
        cwd=project_root,
        timeout=1200,
    )
    advisory_payload = _json_stdout(advisory)
    conflict_payload = _json_stdout(conflict)
    _assert_rag_results(
        query_payload=advisory_payload,
        conflict_payload=conflict_payload,
    )
    _write_json(
        result_root / "rag-advisory-boundary.json",
        {
            "schema_version": "1.0",
            "retrieval_step_sha256": _sha256(evidence_root / "11-rag-advisory-query.json"),
            "published_wiki_chunk": PUBLISHED_WIKI_CHUNK,
            "role": "ADVISORY_ONLY",
            "authorized_intervention": "replace exactly 12.5 percent of collocation points near baseline max_abs",
            "decision_authority": "measured fields plus the user-approved Poisson metric contract",
        },
    )

    poisson_root = result_root / "poisson-independent-seed"
    poisson = _run(
        label="13-poisson-qualification",
        command=[
            sys.executable,
            str(POISSON_ROOT / "run_poisson_qualification.py"),
            "--training-python",
            str(pinn_python),
            "--output-root",
            str(poisson_root),
            "--metric-approval",
            str(POISSON_ROOT / "metric-priority-approval-2026-07-20.json"),
            "--seed",
            str(args.seed),
        ],
        evidence_root=evidence_root,
        cwd=project_root,
        timeout=1800,
    )
    poisson_summary = _json_stdout(poisson)
    poisson_report_path = Path(poisson_summary["report"]).resolve(strict=True)
    poisson_report = json.loads(poisson_report_path.read_text(encoding="utf-8"))
    required = {
        "validation": poisson_report["validation"]["status"] == "RESULT_VALID",
        "replay": poisson_report["replay"]["status"] == "PASS",
        "semantic_isolation": poisson_report["semantic_isolation"]["status"] == "PASS",
        "evidence_integrity": poisson_report["evidence_integrity"]["status"] == "PASS",
    }
    if not all(required.values()):
        raise RuntimeError("Poisson qualification failed a mandatory evidence gate")

    _scan_result_credentials(result_root)
    files = tuple(sorted(path for path in result_root.rglob("*") if path.is_file()))
    completion = {
        "schema_version": "1.0",
        "status": "PASS",
        "completed_at": datetime.now(UTC).isoformat(),
        "duration_seconds": (datetime.now(UTC) - started_at).total_seconds(),
        "repo_commit": args.repo_commit,
        "source_archive_sha256": args.source_archive_sha256,
        "wiki": {
            "chunk_id": PUBLISHED_WIKI_CHUNK,
            "publication_code": "WIKI_PUBLISHED",
            "idempotent_replay_code": "WIKI_VERIFIED",
            "skill_published": False,
        },
        "retrieval": {
            "embedding_model_id": QWEN3_EMBEDDING_MODEL_ID,
            "embedding_revision": QWEN3_EMBEDDING_REVISION,
            "reranker_model_id": QWEN3_RERANKER_MODEL_ID,
            "reranker_revision": QWEN3_RERANKER_REVISION,
            "published_wiki_retrieved": True,
            "conflict_visible": True,
        },
        "poisson": {
            "seed": args.seed,
            "decision": poisson_report["decision"]["status"],
            "validation": poisson_report["validation"]["status"],
            "replay": poisson_report["replay"]["status"],
            "report_sha256": _sha256(poisson_report_path),
            "gates": required,
        },
        "credential_scan": "PASS",
        "file_count_before_completion_manifest": len(files),
        "total_bytes_before_completion_manifest": sum(path.stat().st_size for path in files),
        "files": [
            {
                "relative_path": path.relative_to(result_root).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
    }
    completion_path = result_root / "completion-manifest.json"
    _write_json(completion_path, completion)
    marker = result_root / "FULL_CHAIN_PASS"
    marker.write_text(
        f"completion_manifest_sha256={_sha256(completion_path)}\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "completion_manifest": str(completion_path),
                "completion_sha256": _sha256(completion_path),
                "poisson_decision": poisson_report["decision"]["status"],
            },
            sort_keys=True,
        ),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--source-archive-sha256", required=True)
    parser.add_argument("--repo-commit", required=True)
    parser.add_argument("--qwen-python", type=Path, required=True)
    parser.add_argument("--qwen-cache-root", type=Path, required=True)
    parser.add_argument("--pinn-python", type=Path, required=True)
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=314159)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.repo_commit) is None:
        raise ValueError("repo commit must be a full Git SHA-1")
    if re.fullmatch(r"[0-9a-f]{64}", args.source_archive_sha256) is None:
        raise ValueError("source archive hash must be SHA-256")
    execute(args)


if __name__ == "__main__":
    main()

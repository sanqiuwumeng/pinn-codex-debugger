"""Replay the frozen Qwen3 gates through production provider contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
import time
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
BENCHMARK_ROOT = REPOSITORY_ROOT / "qualification" / "qwen"
sys.path.insert(0, str(ORCHESTRATOR_SRC))
sys.path.insert(0, str(BENCHMARK_ROOT))

from pinn_strategy_system.contracts import SourceRef  # noqa: E402
from pinn_strategy_system.retrieval import (  # noqa: E402
    HybridEvidence,
    QWEN3_EMBEDDING_MODEL_ID,
    QWEN3_EMBEDDING_REVISION,
    QWEN3_RERANKER_MODEL_ID,
    QWEN3_RERANKER_REVISION,
    Qwen3EmbeddingProvider,
    Qwen3RerankerProvider,
    SubprocessJsonlModelTransport,
)
from run_qwen3_retrieval_benchmark import (  # noqa: E402
    all_expected_at_k,
    build_quality_gate,
    detect_conflicts,
    evaluate_single_cases,
    group_recall_at_1,
    lexical_rankings,
    load_packet,
    rankings_from_score_rows,
    reciprocal_rank_fusion,
    rerank_candidate_limit,
)


class RequestIds:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self.count = 0

    def __call__(self, operation: str) -> str:
        self.count += 1
        return f"{self._prefix}-{operation}-{self.count:04d}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dot(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    return sum(left * right for left, right in zip(first, second, strict=True))


def model_transport(
    args: argparse.Namespace,
    *,
    role: str,
    revision: str,
    snapshot: PurePosixPath,
) -> SubprocessJsonlModelTransport:
    gateway_arguments = (
        str(args.remote_python),
        str(args.remote_gateway),
        "--role",
        role,
        "--snapshot",
        str(snapshot),
        "--revision",
        revision,
        "--max-length",
        str(args.max_length),
        "--batch-size",
        str(args.batch_size),
    )
    remote_command = shlex.join(gateway_arguments)
    ssh_arguments = (
        "-T",
        "-o",
        "BatchMode=yes",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={args.known_hosts_file}",
        "-o",
        f"ConnectTimeout={args.connect_timeout_seconds}",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=4",
        "-i",
        str(args.identity_file),
        "-p",
        str(args.port),
        f"{args.username}@{args.hostname}",
        "--",
        remote_command,
    )
    return SubprocessJsonlModelTransport(
        executable=args.ssh_executable.resolve(strict=True),
        arguments=ssh_arguments,
        working_directory=args.output_root,
        environment=_openssh_environment(),
        timeout_seconds=args.operation_timeout_seconds,
    )


def _openssh_environment() -> tuple[tuple[str, str], ...]:
    allowlist = (
        "SYSTEMROOT",
        "WINDIR",
        "PROGRAMDATA",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "PATH",
        "TEMP",
        "TMP",
    )
    return tuple((name, os.environ[name]) for name in allowlist if name in os.environ)


def dense_stage(args, documents, cases):
    request_ids = RequestIds("embedding")
    with model_transport(
        args,
        role="embedding",
        revision=QWEN3_EMBEDDING_REVISION,
        snapshot=args.embedding_snapshot,
    ) as transport:
        provider = Qwen3EmbeddingProvider(
            transport=transport,
            request_id_factory=request_ids,
        )
        document_vectors = provider.embed_documents(
            tuple(f"{item.title}\n{item.text}" for item in documents)
        )
        query_vectors = tuple(provider.embed_query(item.query) for item in cases)
        repeat_vectors = tuple(provider.embed_query(item.query) for item in cases)
    rows = [
        [dot(query, document) for document in document_vectors]
        for query in query_vectors
    ]
    repeat_rows = [
        [dot(query, document) for document in document_vectors]
        for query in repeat_vectors
    ]
    document_ids = [item.document_id for item in documents]
    rankings = rankings_from_score_rows(cases, document_ids, rows)
    repeat_rankings = rankings_from_score_rows(cases, document_ids, repeat_rows)
    return rankings, rankings == repeat_rankings, request_ids.count


def _candidate_evidence(
    document,
    *,
    rank: int,
    packet_sha256: str,
) -> HybridEvidence:
    return HybridEvidence(
        evidence_id=document.document_id,
        source_ref=SourceRef(
            uri=f"artifact://qwen3-frozen-packet/{document.document_id}",
            sha256=packet_sha256,
        ),
        artifact_range=f"corpus[id={document.document_id}]",
        excerpt=f"{document.title}\n{document.text}",
        metadata={
            "document_id": document.document_id,
            "source_kind": document.source_kind,
            "claims": [
                {"key": key, "value": value}
                for key, value in document.claims
            ],
        },
        vector_rank=rank,
        fused_score=1.0 / (60 + rank),
        conflict_keys=tuple(sorted({key for key, _ in document.claims})),
        provenance_validated=True,
    )


def rerank_stage(args, documents, cases, hybrid, packet_sha256):
    documents_by_id = {item.document_id: item for item in documents}
    request_ids = RequestIds("reranker")
    rankings: dict[str, list[str]] = {}
    repeat_rankings: dict[str, list[str]] = {}
    preservation_checks: list[bool] = []
    with model_transport(
        args,
        role="reranker",
        revision=QWEN3_RERANKER_REVISION,
        snapshot=args.reranker_snapshot,
    ) as transport:
        provider = Qwen3RerankerProvider(
            transport=transport,
            request_id_factory=request_ids,
        )
        for case in cases:
            limit = rerank_candidate_limit(case, 6, 10)
            candidates = tuple(
                _candidate_evidence(
                    documents_by_id[document_id],
                    rank=rank,
                    packet_sha256=packet_sha256,
                )
                for rank, document_id in enumerate(
                    hybrid[case.case_id][:limit],
                    start=1,
                )
            )
            ranked = provider.rerank(query=case.query, evidence=candidates)
            repeated = provider.rerank(query=case.query, evidence=candidates)
            rankings[case.case_id] = [
                item.evidence.evidence_id for item in ranked
            ]
            repeat_rankings[case.case_id] = [
                item.evidence.evidence_id for item in repeated
            ]
            originals = {item.evidence_id: item for item in candidates}
            preservation_checks.extend(
                item.evidence == originals[item.evidence.evidence_id]
                for item in ranked
            )
    return (
        rankings,
        rankings == repeat_rankings,
        all(preservation_checks),
        request_ids.count,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh-executable", type=Path, required=True)
    parser.add_argument("--identity-file", type=Path, required=True)
    parser.add_argument("--known-hosts-file", type=Path, required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--remote-python", type=PurePosixPath, required=True)
    parser.add_argument("--remote-gateway", type=PurePosixPath, required=True)
    parser.add_argument("--embedding-snapshot", type=PurePosixPath, required=True)
    parser.add_argument("--reranker-snapshot", type=PurePosixPath, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--connect-timeout-seconds", type=int, default=15)
    parser.add_argument("--operation-timeout-seconds", type=int, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_root = args.output_root.resolve(strict=False)
    if args.output_root.exists():
        raise FileExistsError("provider qualification output root already exists")
    args.output_root.mkdir(parents=True)
    args.identity_file = args.identity_file.resolve(strict=True)
    args.known_hosts_file = args.known_hosts_file.resolve(strict=True)
    cases_path = args.cases.resolve(strict=True)
    packet_sha256 = sha256_file(cases_path)
    schema_version, documents, cases, thresholds = load_packet(cases_path)
    started = time.time()
    lexical = lexical_rankings(documents, cases)
    dense, embedding_repeat, embedding_requests = dense_stage(
        args,
        documents,
        cases,
    )
    hybrid = reciprocal_rank_fusion(lexical, dense)
    (
        reranked,
        reranker_repeat,
        metadata_preserved,
        reranker_requests,
    ) = rerank_stage(
        args,
        documents,
        cases,
        hybrid,
        packet_sha256,
    )
    lexical_metrics = evaluate_single_cases(cases, lexical)
    dense_metrics = evaluate_single_cases(cases, dense)
    hybrid_metrics = evaluate_single_cases(cases, hybrid)
    rerank_metrics = evaluate_single_cases(cases, reranked)
    conflict_case = next(item for item in cases if item.mode == "all")
    documents_by_id = {item.document_id: item for item in documents}
    conflict_coverage = all_expected_at_k(conflict_case, reranked, 5)
    conflicts = detect_conflicts(
        documents_by_id,
        reranked[conflict_case.case_id],
        5,
    )
    cross_language = group_recall_at_1(cases, reranked, "cross_language")
    historical = group_recall_at_1(
        cases,
        reranked,
        "historical_experiment",
    )
    repeated_identically = embedding_repeat and reranker_repeat
    quality_gate = build_quality_gate(
        thresholds,
        dense_metrics,
        hybrid_metrics,
        rerank_metrics,
        cross_language,
        historical,
        conflict_coverage,
        "radiation_temperature_unit" in conflicts,
        repeated_identically,
    )
    quality_gate["provider_metadata_preserved"] = metadata_preserved
    quality_gate["all_passed"] = (
        quality_gate["passed"] and metadata_preserved
    )
    result = {
        "schema_version": "qwen3-production-provider-qualification-v1",
        "packet_schema_version": schema_version,
        "completed_at_unix": time.time(),
        "duration_seconds": time.time() - started,
        "quality_gate": quality_gate,
        "quality_metrics": {
            "lexical": lexical_metrics,
            "dense": dense_metrics,
            "hybrid": hybrid_metrics,
            "rerank": rerank_metrics,
            "cross_language_rerank_at_1": cross_language,
            "historical_rerank_at_1": historical,
            "conflict_all_at_5": conflict_coverage,
            "conflicts": conflicts,
            "repeat_rankings_identical": repeated_identically,
            "provider_metadata_preserved": metadata_preserved,
        },
        "rankings": {
            "lexical": lexical,
            "dense": dense,
            "hybrid": hybrid,
            "rerank": reranked,
        },
        "models": {
            "embedding": {
                "id": QWEN3_EMBEDDING_MODEL_ID,
                "revision": QWEN3_EMBEDDING_REVISION,
            },
            "reranker": {
                "id": QWEN3_RERANKER_MODEL_ID,
                "revision": QWEN3_RERANKER_REVISION,
            },
        },
        "policy": {
            "ordinary_candidates": 6,
            "all_evidence_candidates": 10,
            "max_length": args.max_length,
            "batch_size": args.batch_size,
        },
        "transport": {
            "kind": "persistent-openssh-subprocess-jsonl",
            "embedding_requests": embedding_requests,
            "reranker_requests": reranker_requests,
        },
        "provenance": {
            "cases_sha256": packet_sha256,
            "runner_sha256": sha256_file(Path(__file__).resolve()),
            "gateway_sha256": sha256_file(
                REPOSITORY_ROOT / "retrieval-runtime" / "qwen3_jsonl_gateway.py"
            ),
        },
    }
    result_path = args.output_root / "provider-qualification-result.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "all_passed": quality_gate["all_passed"],
                "result_sha256": sha256_file(result_path),
            },
            sort_keys=True,
        )
    )
    return 0 if quality_gate["all_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

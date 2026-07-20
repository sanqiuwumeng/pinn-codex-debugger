"""Frozen Qwen3 dense retrieval and reranking benchmark.

The runner loads only local immutable snapshots. Model download is a separate
stage so the benchmark itself can run with Hugging Face network access disabled.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import platform
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


@dataclass(frozen=True)
class CorpusDocument:
    document_id: str
    title: str
    text: str
    source_kind: str
    claims: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    group: str
    mode: str
    query: str
    expected_ids: tuple[str, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_packet(
    path: Path,
) -> tuple[
    str,
    tuple[CorpusDocument, ...],
    tuple[BenchmarkCase, ...],
    dict[str, float | bool],
]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents = tuple(
        CorpusDocument(
            document_id=item["id"],
            title=item["title"],
            text=item["text"],
            source_kind=item["source_kind"],
            claims=tuple(
                (claim["key"], claim["value"])
                for claim in item.get("claims", [])
            ),
        )
        for item in payload["corpus"]
    )
    cases = tuple(
        BenchmarkCase(
            case_id=item["id"],
            group=item["group"],
            mode=item["mode"],
            query=item["query"],
            expected_ids=tuple(item["expected_ids"]),
        )
        for item in payload["cases"]
    )
    validate_packet(documents, cases)
    return payload["schema_version"], documents, cases, payload["thresholds"]


def validate_packet(
    documents: Sequence[CorpusDocument], cases: Sequence[BenchmarkCase]
) -> None:
    document_ids = tuple(item.document_id for item in documents)
    if len(document_ids) != len(set(document_ids)):
        raise ValueError("corpus document IDs must be unique")
    case_ids = tuple(item.case_id for item in cases)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("benchmark case IDs must be unique")
    known = set(document_ids)
    for case in cases:
        if case.mode not in {"single", "all"}:
            raise ValueError(f"unsupported case mode: {case.mode}")
        if not case.expected_ids or not set(case.expected_ids) <= known:
            raise ValueError(f"case has unknown expected IDs: {case.case_id}")


def lexical_tokens(text: str) -> frozenset[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9_]+(?:/[a-z0-9_^]+)?", lowered)
    han_runs = re.findall(r"[\u3400-\u9fff]+", lowered)
    han_tokens: list[str] = []
    for run in han_runs:
        han_tokens.extend(run)
        han_tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return frozenset((*latin, *han_tokens))


def lexical_rankings(
    documents: Sequence[CorpusDocument], cases: Sequence[BenchmarkCase]
) -> dict[str, list[str]]:
    document_tokens = {
        item.document_id: lexical_tokens(f"{item.title} {item.text}")
        for item in documents
    }
    rankings: dict[str, list[str]] = {}
    for case in cases:
        query_tokens = lexical_tokens(case.query)
        scored = []
        for document in documents:
            overlap = len(query_tokens & document_tokens[document.document_id])
            denominator = math.sqrt(
                max(1, len(query_tokens))
                * max(1, len(document_tokens[document.document_id]))
            )
            scored.append((overlap / denominator, document.document_id))
        rankings[case.case_id] = [
            document_id
            for _, document_id in sorted(
                scored, key=lambda item: (-item[0], item[1])
            )
        ]
    return rankings


def rankings_from_score_rows(
    cases: Sequence[BenchmarkCase],
    document_ids: Sequence[str],
    score_rows: Sequence[Sequence[float]],
) -> dict[str, list[str]]:
    if len(cases) != len(score_rows):
        raise ValueError("score row count does not match case count")
    rankings: dict[str, list[str]] = {}
    for case, scores in zip(cases, score_rows, strict=True):
        if len(document_ids) != len(scores):
            raise ValueError(f"score width mismatch for {case.case_id}")
        ranked = sorted(
            zip(scores, document_ids, strict=True),
            key=lambda item: (-float(item[0]), item[1]),
        )
        rankings[case.case_id] = [document_id for _, document_id in ranked]
    return rankings


def reciprocal_rank_fusion(
    left: dict[str, list[str]],
    right: dict[str, list[str]],
    *,
    rank_constant: int = 60,
) -> dict[str, list[str]]:
    if left.keys() != right.keys():
        raise ValueError("fusion ranking keys differ")
    fused: dict[str, list[str]] = {}
    for case_id in left:
        scores: defaultdict[str, float] = defaultdict(float)
        for ranking in (left[case_id], right[case_id]):
            for rank, document_id in enumerate(ranking, start=1):
                scores[document_id] += 1.0 / (rank_constant + rank)
        fused[case_id] = [
            document_id
            for document_id, _ in sorted(
                scores.items(), key=lambda item: (-item[1], item[0])
            )
        ]
    return fused


def evaluate_single_cases(
    cases: Sequence[BenchmarkCase], rankings: dict[str, list[str]]
) -> dict[str, Any]:
    selected = [case for case in cases if case.mode == "single"]
    reciprocal_ranks: list[float] = []
    recall_at_1 = 0
    recall_at_3 = 0
    detail: dict[str, Any] = {}
    for case in selected:
        ranking = rankings[case.case_id]
        expected = set(case.expected_ids)
        positions = [
            index
            for index, document_id in enumerate(ranking, start=1)
            if document_id in expected
        ]
        first = min(positions) if positions else None
        reciprocal_ranks.append(0.0 if first is None else 1.0 / first)
        recall_at_1 += int(first is not None and first <= 1)
        recall_at_3 += int(first is not None and first <= 3)
        detail[case.case_id] = {
            "group": case.group,
            "first_relevant_rank": first,
            "top5": ranking[:5],
        }
    denominator = max(1, len(selected))
    return {
        "case_count": len(selected),
        "recall_at_1": recall_at_1 / denominator,
        "recall_at_3": recall_at_3 / denominator,
        "mrr": sum(reciprocal_ranks) / denominator,
        "cases": detail,
    }


def group_recall_at_1(
    cases: Sequence[BenchmarkCase],
    rankings: dict[str, list[str]],
    group: str,
) -> float:
    selected = [
        case for case in cases if case.mode == "single" and case.group == group
    ]
    if not selected:
        raise ValueError(f"benchmark group is empty: {group}")
    hits = sum(
        int(rankings[case.case_id][0] in set(case.expected_ids))
        for case in selected
    )
    return hits / len(selected)


def all_expected_at_k(
    case: BenchmarkCase, rankings: dict[str, list[str]], k: int
) -> float:
    expected = set(case.expected_ids)
    found = expected & set(rankings[case.case_id][:k])
    return len(found) / len(expected)


def detect_conflicts(
    documents_by_id: dict[str, CorpusDocument], ranking: Sequence[str], k: int
) -> dict[str, list[str]]:
    observed: defaultdict[str, set[str]] = defaultdict(set)
    for document_id in ranking[:k]:
        for key, value in documents_by_id[document_id].claims:
            observed[key].add(value)
    return {
        key: sorted(values)
        for key, values in sorted(observed.items())
        if len(values) > 1
    }


def memory_snapshot(torch: Any) -> dict[str, float]:
    return {
        "allocated_mib": round(torch.cuda.memory_allocated(0) / 1024**2, 3),
        "reserved_mib": round(torch.cuda.memory_reserved(0) / 1024**2, 3),
        "peak_allocated_mib": round(
            torch.cuda.max_memory_allocated(0) / 1024**2, 3
        ),
        "peak_reserved_mib": round(
            torch.cuda.max_memory_reserved(0) / 1024**2, 3
        ),
    }


def prepare_cuda_memory_tracking(cuda: Any) -> None:
    """Initialize CUDA before resetting allocator peak statistics."""
    cuda.init()
    cuda.empty_cache()
    cuda.reset_peak_memory_stats()


def release_cuda(torch: Any, *objects: Any) -> dict[str, float]:
    del objects
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize(0)
    return memory_snapshot(torch)


def run_dense_embedding(
    snapshot: Path,
    documents: Sequence[CorpusDocument],
    cases: Sequence[BenchmarkCase],
    *,
    max_length: int,
    batch_size: int,
) -> tuple[list[list[float]], dict[str, Any], bool]:
    import torch
    from sentence_transformers import SentenceTransformer

    prepare_cuda_memory_tracking(torch.cuda)
    load_started = time.perf_counter()
    model = SentenceTransformer(
        str(snapshot),
        device="cuda",
        local_files_only=True,
        model_kwargs={
            "torch_dtype": torch.bfloat16,
            "attn_implementation": "sdpa",
        },
        tokenizer_kwargs={"padding_side": "left"},
    )
    model.max_seq_length = max_length
    load_seconds = time.perf_counter() - load_started

    document_texts = [f"{item.title}\n{item.text}" for item in documents]
    query_texts = [item.query for item in cases]
    encode_started = time.perf_counter()
    with torch.inference_mode():
        document_embeddings = model.encode(
            document_texts,
            batch_size=batch_size,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        query_embeddings = model.encode(
            query_texts,
            prompt_name="query",
            batch_size=batch_size,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        repeat_query_embeddings = model.encode(
            query_texts,
            prompt_name="query",
            batch_size=batch_size,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        score_tensor = query_embeddings @ document_embeddings.T
        repeat_score_tensor = repeat_query_embeddings @ document_embeddings.T
    torch.cuda.synchronize(0)
    encode_seconds = time.perf_counter() - encode_started
    score_rows = score_tensor.float().cpu().tolist()
    repeat_rows = repeat_score_tensor.float().cpu().tolist()
    repeated_identically = rankings_from_score_rows(
        cases,
        [item.document_id for item in documents],
        score_rows,
    ) == rankings_from_score_rows(
        cases,
        [item.document_id for item in documents],
        repeat_rows,
    )
    metrics = {
        "load_seconds": load_seconds,
        "encode_two_query_passes_seconds": encode_seconds,
        "document_count": len(document_texts),
        "query_count": len(query_texts),
        "embedding_dimension": int(document_embeddings.shape[1]),
        "memory_before_release": memory_snapshot(torch),
    }
    del (
        repeat_score_tensor,
        score_tensor,
        repeat_query_embeddings,
        query_embeddings,
        document_embeddings,
        model,
    )
    metrics["memory_after_release"] = release_cuda(torch)
    return score_rows, metrics, repeated_identically


def format_reranker_input(query: str, document: CorpusDocument) -> str:
    instruction = (
        "Given a PINN debugging and experiment-governance query, retrieve "
        "evidence that directly addresses the query."
    )
    return (
        f"<Instruct>: {instruction}\n<Query>: {query}\n"
        f"<Document>: {document.title}\n{document.text}"
    )


def score_reranker_pairs(
    model: Any,
    tokenizer: Any,
    pairs: Sequence[str],
    *,
    max_length: int,
    batch_size: int,
) -> list[float]:
    import torch

    prefix = (
        "<|im_start|>system\nJudge whether the Document meets the requirements "
        "based on the Query and the Instruct provided. Note that the answer "
        "can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n"
    )
    suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    prefix_tokens = tokenizer.encode(prefix, add_special_tokens=False)
    suffix_tokens = tokenizer.encode(suffix, add_special_tokens=False)
    body_limit = max_length - len(prefix_tokens) - len(suffix_tokens)
    if body_limit <= 0:
        raise ValueError("reranker max length is shorter than prompt framing")
    false_id = tokenizer.convert_tokens_to_ids("no")
    true_id = tokenizer.convert_tokens_to_ids("yes")
    scores: list[float] = []
    for start in range(0, len(pairs), batch_size):
        batch = pairs[start : start + batch_size]
        bodies = tokenizer(
            list(batch),
            add_special_tokens=False,
            truncation=True,
            max_length=body_limit,
            padding=False,
        )["input_ids"]
        features = [
            {"input_ids": prefix_tokens + body + suffix_tokens}
            for body in bodies
        ]
        model_inputs = tokenizer.pad(
            features,
            padding=True,
            return_tensors="pt",
        ).to(model.device)
        with torch.inference_mode():
            logits = model(**model_inputs).logits[:, -1, :]
            batch_scores = logits[:, true_id] - logits[:, false_id]
        scores.extend(float(value) for value in batch_scores.float().cpu())
    return scores


def rerank_candidate_limit(
    case: BenchmarkCase,
    single_evidence_count: int,
    all_evidence_count: int,
) -> int:
    return {
        "single": single_evidence_count,
        "all": all_evidence_count,
    }[case.mode]


def run_reranker(
    snapshot: Path,
    documents_by_id: dict[str, CorpusDocument],
    cases: Sequence[BenchmarkCase],
    candidate_rankings: dict[str, list[str]],
    *,
    candidate_count: int,
    all_evidence_candidate_count: int,
    max_length: int,
    batch_size: int,
) -> tuple[dict[str, list[str]], dict[str, Any], bool]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    prepare_cuda_memory_tracking(torch.cuda)
    load_started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        str(snapshot),
        local_files_only=True,
        padding_side="left",
    )
    model = AutoModelForCausalLM.from_pretrained(
        str(snapshot),
        local_files_only=True,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        device_map={"": 0},
    ).eval()
    load_seconds = time.perf_counter() - load_started

    pairs: list[str] = []
    pair_keys: list[tuple[str, str]] = []
    for case in cases:
        limit = rerank_candidate_limit(
            case,
            candidate_count,
            all_evidence_candidate_count,
        )
        for document_id in candidate_rankings[case.case_id][:limit]:
            pairs.append(
                format_reranker_input(case.query, documents_by_id[document_id])
            )
            pair_keys.append((case.case_id, document_id))
    score_started = time.perf_counter()
    scores = score_reranker_pairs(
        model,
        tokenizer,
        pairs,
        max_length=max_length,
        batch_size=batch_size,
    )
    repeat_scores = score_reranker_pairs(
        model,
        tokenizer,
        pairs,
        max_length=max_length,
        batch_size=batch_size,
    )
    torch.cuda.synchronize(0)
    score_seconds = time.perf_counter() - score_started

    per_case: defaultdict[str, list[tuple[float, str]]] = defaultdict(list)
    repeated_per_case: defaultdict[str, list[tuple[float, str]]] = defaultdict(list)
    for (case_id, document_id), score, repeat_score in zip(
        pair_keys, scores, repeat_scores, strict=True
    ):
        per_case[case_id].append((score, document_id))
        repeated_per_case[case_id].append((repeat_score, document_id))
    rankings = {
        case_id: [
            document_id
            for _, document_id in sorted(
                items, key=lambda item: (-item[0], item[1])
            )
        ]
        for case_id, items in per_case.items()
    }
    repeat_rankings = {
        case_id: [
            document_id
            for _, document_id in sorted(
                items, key=lambda item: (-item[0], item[1])
            )
        ]
        for case_id, items in repeated_per_case.items()
    }
    metrics = {
        "load_seconds": load_seconds,
        "score_two_passes_seconds": score_seconds,
        "pair_count": len(pairs),
        "max_score_delta": max(
            abs(first - second)
            for first, second in zip(scores, repeat_scores, strict=True)
        ),
        "memory_before_release": memory_snapshot(torch),
    }
    del model, tokenizer
    metrics["memory_after_release"] = release_cuda(torch)
    return rankings, metrics, rankings == repeat_rankings


def build_quality_gate(
    thresholds: dict[str, float | bool],
    dense_metrics: dict[str, Any],
    hybrid_metrics: dict[str, Any],
    rerank_metrics: dict[str, Any],
    cross_language: float,
    historical: float,
    conflict_all_at_5: float,
    conflict_key_detected: bool,
    repeated_identically: bool,
) -> dict[str, Any]:
    observed: dict[str, float | bool] = {
        "dense_recall_at_3": dense_metrics["recall_at_3"],
        "hybrid_recall_at_3": hybrid_metrics["recall_at_3"],
        "rerank_recall_at_1": rerank_metrics["recall_at_1"],
        "cross_language_rerank_at_1": cross_language,
        "historical_rerank_at_1": historical,
        "conflict_all_at_5": conflict_all_at_5,
        "conflict_key_detected": conflict_key_detected,
        "repeat_rankings_identical": repeated_identically,
    }
    checks: dict[str, bool] = {}
    for key, threshold in thresholds.items():
        value = observed[key]
        if isinstance(threshold, bool):
            checks[key] = value is threshold
        else:
            checks[key] = float(value) >= float(threshold)
    return {
        "passed": all(checks.values()),
        "thresholds": thresholds,
        "observed": observed,
        "checks": checks,
    }


def render_summary(result: dict[str, Any]) -> str:
    quality = result["quality_gate"]
    metrics = result["quality_metrics"]
    resources = result["resource_metrics"]
    return "\n".join(
        (
            "# Qwen3 Retrieval Benchmark Summary",
            "",
            f"- Status: {'PASS' if quality['passed'] else 'FAIL'}",
            f"- Packet SHA256: `{result['provenance']['cases_sha256']}`",
            f"- Embedding revision: `{result['models']['embedding']['revision']}`",
            f"- Reranker revision: `{result['models']['reranker']['revision']}`",
            "",
            "## Retrieval quality",
            "",
            f"- Lexical recall@1 / recall@3 / MRR: {metrics['lexical']['recall_at_1']:.4f} / {metrics['lexical']['recall_at_3']:.4f} / {metrics['lexical']['mrr']:.4f}",
            f"- Dense recall@1 / recall@3 / MRR: {metrics['dense']['recall_at_1']:.4f} / {metrics['dense']['recall_at_3']:.4f} / {metrics['dense']['mrr']:.4f}",
            f"- Hybrid recall@1 / recall@3 / MRR: {metrics['hybrid']['recall_at_1']:.4f} / {metrics['hybrid']['recall_at_3']:.4f} / {metrics['hybrid']['mrr']:.4f}",
            f"- Rerank recall@1 / recall@3 / MRR: {metrics['rerank']['recall_at_1']:.4f} / {metrics['rerank']['recall_at_3']:.4f} / {metrics['rerank']['mrr']:.4f}",
            f"- Conflict evidence coverage@5: {metrics['conflict_all_at_5']:.4f}",
            f"- Conflict detected: {metrics['conflicts']}",
            "",
            "## Resource evidence",
            "",
            f"- Embedding load seconds: {resources['embedding']['load_seconds']:.3f}",
            f"- Embedding peak allocated MiB: {resources['embedding']['memory_before_release']['peak_allocated_mib']:.3f}",
            f"- Reranker load seconds: {resources['reranker']['load_seconds']:.3f}",
            f"- Reranker peak allocated MiB: {resources['reranker']['memory_before_release']['peak_allocated_mib']:.3f}",
            "",
        )
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--embedding-snapshot", type=Path, required=True)
    parser.add_argument("--embedding-revision", required=True)
    parser.add_argument("--reranker-snapshot", type=Path, required=True)
    parser.add_argument("--reranker-revision", required=True)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--embedding-batch-size", type=int, default=4)
    parser.add_argument("--reranker-batch-size", type=int, default=4)
    parser.add_argument("--rerank-candidates", type=int, default=6)
    parser.add_argument("--all-evidence-rerank-candidates", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    args.result_dir.mkdir(parents=True, exist_ok=False)
    schema_version, documents, cases, thresholds = load_packet(args.cases)
    if args.embedding_snapshot.name != args.embedding_revision:
        raise ValueError("embedding snapshot path does not match locked revision")
    if args.reranker_snapshot.name != args.reranker_revision:
        raise ValueError("reranker snapshot path does not match locked revision")
    if args.all_evidence_rerank_candidates < args.rerank_candidates:
        raise ValueError(
            "all-evidence rerank candidates cannot be smaller than the "
            "single-evidence candidate count"
        )

    document_ids = [item.document_id for item in documents]
    documents_by_id = {item.document_id: item for item in documents}
    lexical = lexical_rankings(documents, cases)
    dense_scores, embedding_resources, embedding_repeat = run_dense_embedding(
        args.embedding_snapshot,
        documents,
        cases,
        max_length=args.max_length,
        batch_size=args.embedding_batch_size,
    )
    dense = rankings_from_score_rows(cases, document_ids, dense_scores)
    hybrid = reciprocal_rank_fusion(lexical, dense)
    reranked, reranker_resources, reranker_repeat = run_reranker(
        args.reranker_snapshot,
        documents_by_id,
        cases,
        hybrid,
        candidate_count=args.rerank_candidates,
        all_evidence_candidate_count=args.all_evidence_rerank_candidates,
        max_length=args.max_length,
        batch_size=args.reranker_batch_size,
    )

    lexical_metrics = evaluate_single_cases(cases, lexical)
    dense_metrics = evaluate_single_cases(cases, dense)
    hybrid_metrics = evaluate_single_cases(cases, hybrid)
    rerank_metrics = evaluate_single_cases(cases, reranked)
    conflict_case = next(case for case in cases if case.mode == "all")
    conflict_coverage = all_expected_at_k(conflict_case, reranked, 5)
    conflicts = detect_conflicts(
        documents_by_id, reranked[conflict_case.case_id], 5
    )
    repeated_identically = embedding_repeat and reranker_repeat
    cross_language = group_recall_at_1(cases, reranked, "cross_language")
    historical = group_recall_at_1(cases, reranked, "historical_experiment")
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

    import psutil
    import torch
    from importlib import metadata

    result: dict[str, Any] = {
        "schema_version": schema_version,
        "completed_at_unix": time.time(),
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
        },
        "rankings": {
            "lexical": lexical,
            "dense": dense,
            "hybrid": hybrid,
            "rerank": reranked,
        },
        "resource_metrics": {
            "embedding": embedding_resources,
            "reranker": reranker_resources,
            "process_rss_mib": round(
                psutil.Process().memory_info().rss / 1024**2, 3
            ),
        },
        "models": {
            "embedding": {
                "id": "Qwen/Qwen3-Embedding-8B",
                "revision": args.embedding_revision,
                "snapshot": str(args.embedding_snapshot),
            },
            "reranker": {
                "id": "Qwen/Qwen3-Reranker-4B",
                "revision": args.reranker_revision,
                "snapshot": str(args.reranker_snapshot),
            },
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": metadata.version("torch"),
            "transformers": metadata.version("transformers"),
            "sentence_transformers": metadata.version("sentence-transformers"),
            "cuda_runtime": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "compute_capability": list(torch.cuda.get_device_capability(0)),
            "max_length": args.max_length,
            "rerank_candidates": args.rerank_candidates,
            "all_evidence_rerank_candidates": (
                args.all_evidence_rerank_candidates
            ),
        },
        "provenance": {
            "cases_path": str(args.cases),
            "cases_sha256": sha256_file(args.cases),
            "runner_path": str(Path(__file__).resolve()),
            "runner_sha256": sha256_file(Path(__file__).resolve()),
        },
    }
    result_path = args.result_dir / "benchmark-result.json"
    result_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (args.result_dir / "benchmark-summary.md").write_text(
        render_summary(result), encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "quality_gate_passed": quality_gate["passed"],
                "result_path": str(result_path),
                "cases_sha256": result["provenance"]["cases_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

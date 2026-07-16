"""Dependency-isolated persistent JSONL gateway for the approved Qwen3 pair."""

from __future__ import annotations

import argparse
import json
import math
import sys
from importlib import metadata
from pathlib import Path


EMBEDDING_MODEL_ID = "Qwen/Qwen3-Embedding-8B"
EMBEDDING_REVISION = "1d8ad4ca9b3dd8059ad90a75d4983776a23d44af"
RERANKER_MODEL_ID = "Qwen/Qwen3-Reranker-4B"
RERANKER_REVISION = "22e683669bc0f0bd69640a1354a6d0aebcfeede5"
EMBEDDING_DIMENSION = 4096


def _provenance(role: str) -> dict:
    return {
        "schema_version": "1.0",
        "model_id": (
            EMBEDDING_MODEL_ID if role == "embedding" else RERANKER_MODEL_ID
        ),
        "revision": (
            EMBEDDING_REVISION if role == "embedding" else RERANKER_REVISION
        ),
        "runtime_id": "qwen3-jsonl-gateway",
        "runtime_version": (
            f"transformers-{metadata.version('transformers')}"
        ),
        "precision": "bfloat16",
    }


class EmbeddingRuntime:
    def __init__(self, snapshot: Path, max_length: int, batch_size: int) -> None:
        import torch
        from sentence_transformers import SentenceTransformer

        self._torch = torch
        self._batch_size = batch_size
        self._model = SentenceTransformer(
            str(snapshot),
            device="cuda",
            local_files_only=True,
            model_kwargs={
                "torch_dtype": torch.bfloat16,
                "attn_implementation": "sdpa",
            },
            tokenizer_kwargs={"padding_side": "left"},
        )
        self._model.max_seq_length = max_length

    def handle(self, request: dict) -> dict:
        if request.get("operation") == "health":
            return _health(request, "embedding")
        _require_request_identity(request, "embedding")
        texts = request.get("texts")
        if not isinstance(texts, list) or not texts or not all(
            isinstance(item, str) and item for item in texts
        ):
            raise ValueError("embedding texts are invalid")
        if request.get("output_dimension") != EMBEDDING_DIMENSION:
            raise ValueError("embedding dimension is not approved")
        input_type = request.get("input_type")
        if input_type not in {"document", "query"}:
            raise ValueError("embedding input_type is invalid")
        options = {
            "batch_size": self._batch_size,
            "convert_to_tensor": True,
            "normalize_embeddings": True,
            "show_progress_bar": False,
        }
        if input_type == "query":
            options["prompt_name"] = "query"
        with self._torch.inference_mode():
            tensor = self._model.encode(texts, **options)
        vectors = tensor.float().cpu().tolist()
        if any(
            len(vector) != EMBEDDING_DIMENSION
            or any(not math.isfinite(value) for value in vector)
            for vector in vectors
        ):
            raise RuntimeError("embedding output validation failed")
        return {
            "schema_version": "1.0",
            "operation": "embed",
            "request_id": request["request_id"],
            "provenance": _provenance("embedding"),
            "output_dimension": EMBEDDING_DIMENSION,
            "vectors": vectors,
        }


class RerankerRuntime:
    def __init__(self, snapshot: Path, max_length: int, batch_size: int) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._torch = torch
        self._batch_size = batch_size
        self._max_length = max_length
        self._tokenizer = AutoTokenizer.from_pretrained(
            str(snapshot),
            local_files_only=True,
            padding_side="left",
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            str(snapshot),
            local_files_only=True,
            dtype=torch.bfloat16,
            attn_implementation="sdpa",
            device_map={"": 0},
        ).eval()
        self._prefix = (
            "<|im_start|>system\nJudge whether the Document meets the requirements "
            "based on the Query and the Instruct provided. Note that the answer "
            "can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n"
        )
        self._suffix = (
            "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        )

    def handle(self, request: dict) -> dict:
        if request.get("operation") == "health":
            return _health(request, "reranker")
        _require_request_identity(request, "reranker")
        query = request.get("query")
        documents = request.get("documents")
        if not isinstance(query, str) or not query:
            raise ValueError("rerank query is invalid")
        if not isinstance(documents, list) or not documents:
            raise ValueError("rerank documents are invalid")
        identifiers = [item.get("document_id") for item in documents]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("rerank document identifiers are not unique")
        instruction = (
            "Given a PINN debugging and experiment-governance query, retrieve "
            "evidence that directly addresses the query."
        )
        pairs = [
            f"<Instruct>: {instruction}\n<Query>: {query}\n"
            f"<Document>: {item['text']}"
            for item in documents
        ]
        scores = self._score(pairs)
        return {
            "schema_version": "1.0",
            "operation": "rerank",
            "request_id": request["request_id"],
            "provenance": _provenance("reranker"),
            "scores": [
                {
                    "schema_version": "1.0",
                    "document_id": document_id,
                    "score": score,
                }
                for document_id, score in zip(identifiers, scores, strict=True)
            ],
        }

    def _score(self, pairs: list[str]) -> list[float]:
        prefix_tokens = self._tokenizer.encode(
            self._prefix,
            add_special_tokens=False,
        )
        suffix_tokens = self._tokenizer.encode(
            self._suffix,
            add_special_tokens=False,
        )
        body_limit = self._max_length - len(prefix_tokens) - len(suffix_tokens)
        if body_limit <= 0:
            raise ValueError("reranker max length is too small")
        false_id = self._tokenizer.convert_tokens_to_ids("no")
        true_id = self._tokenizer.convert_tokens_to_ids("yes")
        scores: list[float] = []
        for start in range(0, len(pairs), self._batch_size):
            batch = pairs[start : start + self._batch_size]
            bodies = self._tokenizer(
                batch,
                add_special_tokens=False,
                truncation=True,
                max_length=body_limit,
                padding=False,
            )["input_ids"]
            features = [
                {"input_ids": prefix_tokens + body + suffix_tokens}
                for body in bodies
            ]
            model_inputs = self._tokenizer.pad(
                features,
                padding=True,
                return_tensors="pt",
            ).to(self._model.device)
            with self._torch.inference_mode():
                logits = self._model(**model_inputs).logits[:, -1, :]
                batch_scores = logits[:, true_id] - logits[:, false_id]
            scores.extend(float(value) for value in batch_scores.float().cpu())
        if any(not math.isfinite(value) for value in scores):
            raise RuntimeError("reranker output validation failed")
        return scores


def _health(request: dict, role: str) -> dict:
    if request.get("model_role") != role:
        raise ValueError("health role does not match loaded model")
    return {
        "schema_version": "1.0",
        "operation": "health",
        "request_id": request["request_id"],
        "status": "ready",
        "provenance": _provenance(role),
    }


def _require_request_identity(request: dict, role: str) -> None:
    expected = (
        (EMBEDDING_MODEL_ID, EMBEDDING_REVISION)
        if role == "embedding"
        else (RERANKER_MODEL_ID, RERANKER_REVISION)
    )
    if (request.get("model_id"), request.get("revision")) != expected:
        raise ValueError("request model identity is not approved")


def _error(request_id: str) -> dict:
    return {
        "schema_version": "1.0",
        "operation": "error",
        "request_id": request_id,
        "error_code": "MODEL_REQUEST_FAILED",
        "message": "isolated model request failed validation or inference",
        "retryable": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("embedding", "reranker"), required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--batch-size", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = args.snapshot.resolve(strict=True)
    expected_revision = (
        EMBEDDING_REVISION if args.role == "embedding" else RERANKER_REVISION
    )
    if not snapshot.is_dir() or snapshot.name != expected_revision:
        raise ValueError("snapshot path does not match approved revision")
    if args.revision != expected_revision:
        raise ValueError("gateway revision does not match approved revision")
    if args.max_length < 128 or args.batch_size < 1:
        raise ValueError("gateway runtime limits are invalid")
    runtime = (
        EmbeddingRuntime(snapshot, args.max_length, args.batch_size)
        if args.role == "embedding"
        else RerankerRuntime(snapshot, args.max_length, args.batch_size)
    )
    for line in sys.stdin:
        request_id = "unknown-request"
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request is not an object")
            request_id = request.get("request_id", request_id)
            if not isinstance(request_id, str) or not request_id:
                raise ValueError("request_id is invalid")
            response = runtime.handle(request)
        except Exception:
            response = _error(request_id)
        print(
            json.dumps(response, ensure_ascii=False, separators=(",", ":")),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

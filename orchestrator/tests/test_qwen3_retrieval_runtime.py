from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.contracts import SourceRef  # noqa: E402
from pinn_strategy_system.retrieval import (  # noqa: E402
    EmbeddingRequest,
    EmbeddingResponse,
    HybridEvidence,
    ModelHealthRequest,
    ModelHealthResponse,
    ModelProvenance,
    ModelTransportError,
    QWEN3_EMBEDDING_DIMENSION,
    QWEN3_EMBEDDING_MODEL_ID,
    QWEN3_EMBEDDING_REVISION,
    QWEN3_RERANKER_MODEL_ID,
    QWEN3_RERANKER_REVISION,
    Qwen3EmbeddingProvider,
    Qwen3RerankerProvider,
    RemoteJsonlModelTransport,
    RerankResponse,
    RerankScore,
    SubprocessJsonlModelTransport,
)


def _provenance(model_id: str, revision: str) -> ModelProvenance:
    return ModelProvenance(
        model_id=model_id,
        revision=revision,
        runtime_id="isolated-test-runtime",
        runtime_version="1.0.0",
        precision="float32",
    )


class RecordingTransport:
    def __init__(self, *, wrong_provenance: bool = False) -> None:
        self.requests = []
        self.wrong_provenance = wrong_provenance

    def exchange(self, request, *, response_type):
        self.requests.append(request)
        if isinstance(request, EmbeddingRequest):
            revision = (
                "f" * 40 if self.wrong_provenance else QWEN3_EMBEDDING_REVISION
            )
            return EmbeddingResponse(
                request_id=request.request_id,
                provenance=_provenance(QWEN3_EMBEDDING_MODEL_ID, revision),
                output_dimension=request.output_dimension,
                vectors=tuple(
                    tuple(float(index == 0) for index in range(request.output_dimension))
                    for _ in request.texts
                ),
            )
        return RerankResponse(
            request_id=request.request_id,
            provenance=_provenance(
                QWEN3_RERANKER_MODEL_ID,
                QWEN3_RERANKER_REVISION,
            ),
            scores=tuple(
                RerankScore(document_id=item.document_id, score=float(index))
                for index, item in enumerate(request.documents)
            ),
        )


class RaisingRemote:
    def exchange_jsonl(self, request_line: str, timeout_seconds: float) -> str:
        raise ValueError("sensitive-field=must-not-escape")


class InvalidResponseRemote:
    def exchange_jsonl(self, request_line: str, timeout_seconds: float) -> str:
        return json.dumps(
            {
                "schema_version": "1.0",
                "operation": "health",
                "request_id": "health-invalid",
                "status": "sensitive-field=must-not-escape",
                "provenance": None,
            }
        )


class Qwen3RuntimeTests(unittest.TestCase):
    def test_embedding_provider_pins_model_revision_and_validates_dimension(self) -> None:
        transport = RecordingTransport()
        provider = Qwen3EmbeddingProvider(
            transport=transport,
            request_id_factory=lambda operation: f"fixed-{operation}",
        )
        vectors = provider.embed_documents(("alpha", "beta"))
        self.assertEqual(len(vectors), 2)
        self.assertEqual(len(vectors[0]), QWEN3_EMBEDDING_DIMENSION)
        request = transport.requests[0]
        self.assertEqual(request.model_id, QWEN3_EMBEDDING_MODEL_ID)
        self.assertEqual(request.revision, QWEN3_EMBEDDING_REVISION)
        self.assertEqual(request.request_id, "fixed-embed")

    def test_embedding_provider_rejects_wrong_model_provenance(self) -> None:
        provider = Qwen3EmbeddingProvider(
            transport=RecordingTransport(wrong_provenance=True),
        )
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            provider.embed_query("query")

    def test_reranker_preserves_source_conflict_and_metadata(self) -> None:
        evidence = tuple(
            HybridEvidence(
                evidence_id=f"evidence-{index}",
                source_ref=SourceRef(
                    uri=f"artifact://test/{index}",
                    sha256=str(index) * 64,
                    line_start=1,
                    line_end=1,
                ),
                excerpt=f"candidate {index}",
                metadata={"origin": f"source-{index}"},
                vector_rank=index + 1,
                fused_score=1.0 / (index + 1),
                conflict_keys=("unit",) if index == 0 else (),
                provenance_validated=True,
            )
            for index in range(2)
        )
        ranked = Qwen3RerankerProvider(
            transport=RecordingTransport(),
            request_id_factory=lambda operation: f"fixed-{operation}",
        ).rerank(query="candidate", evidence=evidence)
        self.assertEqual(ranked[0].evidence.evidence_id, "evidence-1")
        original = ranked[1].evidence
        self.assertEqual(original.source_ref, evidence[0].source_ref)
        self.assertEqual(original.metadata, evidence[0].metadata)
        self.assertEqual(original.conflict_keys, ("unit",))

    def test_remote_transport_sanitizes_boundary_error(self) -> None:
        transport = RemoteJsonlModelTransport(remote=RaisingRemote())
        request = ModelHealthRequest(
            request_id="health-1",
            model_role="embedding",
        )
        with self.assertRaises(ModelTransportError) as caught:
            transport.exchange(request, response_type=ModelHealthResponse)
        self.assertNotIn("must-not-escape", str(caught.exception))
        self.assertNotIn("sensitive-field", str(caught.exception).casefold())

    def test_remote_transport_sanitizes_contract_validation_error(self) -> None:
        transport = RemoteJsonlModelTransport(remote=InvalidResponseRemote())
        request = ModelHealthRequest(
            request_id="health-invalid",
            model_role="embedding",
        )
        with self.assertRaises(ModelTransportError) as caught:
            transport.exchange(request, response_type=ModelHealthResponse)
        self.assertNotIn("must-not-escape", str(caught.exception))
        self.assertNotIn("sensitive-field", str(caught.exception).casefold())

    def test_subprocess_transport_round_trips_request_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gateway = root / "gateway.py"
            gateway.write_text(
                "\n".join(
                    (
                        "import json, sys",
                        "for line in sys.stdin:",
                        "    request = json.loads(line)",
                        "    response = {",
                        "      'schema_version': '1.0',",
                        "      'operation': 'health',",
                        "      'request_id': request['request_id'],",
                        "      'status': 'ready',",
                        "      'provenance': {",
                        "        'schema_version': '1.0',",
                        f"        'model_id': '{QWEN3_EMBEDDING_MODEL_ID}',",
                        f"        'revision': '{QWEN3_EMBEDDING_REVISION}',",
                        "        'runtime_id': 'gateway-test',",
                        "        'runtime_version': '1.0',",
                        "        'precision': 'float32'",
                        "      }",
                        "    }",
                        "    print(json.dumps(response), flush=True)",
                    )
                ),
                encoding="utf-8",
            )
            environment = tuple(
                (name, os.environ[name])
                for name in ("SYSTEMROOT", "WINDIR", "PATH")
                if name in os.environ
            )
            with SubprocessJsonlModelTransport(
                executable=Path(sys.executable),
                arguments=(str(gateway),),
                working_directory=root,
                environment=environment,
                timeout_seconds=5,
            ) as transport:
                response = transport.exchange(
                    ModelHealthRequest(
                        request_id="health-subprocess",
                        model_role="embedding",
                    ),
                    response_type=ModelHealthResponse,
                )
            self.assertEqual(response.request_id, "health-subprocess")
            self.assertEqual(response.status, "ready")

    def test_remote_transport_rejects_oversized_request(self) -> None:
        transport = RemoteJsonlModelTransport(
            remote=RaisingRemote(),
            max_request_bytes=64,
        )
        request = ModelHealthRequest(
            request_id="health-size-limit",
            model_role="embedding",
        )
        with self.assertRaisesRegex(ModelTransportError, "size limit"):
            transport.exchange(request, response_type=ModelHealthResponse)


if __name__ == "__main__":
    unittest.main()

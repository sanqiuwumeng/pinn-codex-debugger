# Qwen3 Production Provider Qualification

- Date: 2026-07-16
- Outcome: **PASS**
- Scope: OpenSpec tasks 5.1-5.7
- Result root: `validation/phase2/results/qwen3-production-provider-20260716T233200Z/`

## Implemented production boundary

The orchestration environment now communicates with the isolated model runtime
only through strict versioned JSONL contracts and an injected `ModelTransport`.
Embedding, reranking, health and error payloads are immutable Pydantic models.
Both persistent subprocess and injected remote transports enforce request IDs,
timeouts, byte limits, single-record JSONL framing and sanitized exceptions.

The providers accept only these immutable identities:

| Role | Model | Revision | Dimension |
| --- | --- | --- | ---: |
| Embedding | `Qwen/Qwen3-Embedding-8B` | `1d8ad4ca9b3dd8059ad90a75d4983776a23d44af` | 4096 |
| Reranking | `Qwen/Qwen3-Reranker-4B` | `22e683669bc0f0bd69640a1354a6d0aebcfeede5` | n/a |

The Qwen gateway lives outside the orchestration Python package and imports
PyTorch, Transformers and Sentence Transformers only in the previously
approved remote Python 3.11.11 model sandbox. The orchestration environment and
the existing `pytorch2.3.1` training environment were not modified.

## Retrieval and index policy

- Ordinary queries rerank at least six fused candidates.
- Conflict and all-evidence queries rerank at least ten candidates.
- Conflict detection occurs before decision-safe evaluation.
- Conflict-bearing evidence is retained ahead of non-conflicting evidence when
  a response limit is applied.
- Reranking reconstructs results from the original immutable evidence objects,
  preserving source references, artifact ranges, metadata, claims and conflict
  keys.
- Qdrant collection identity now covers the embedding model and revision,
  vector dimension, chunking policy, metadata schema and authoritative source
  identities.
- Rebuild creates or reuses a content-addressed candidate collection. Only a
  passing canary can atomically activate it. The previous collection remains
  available, activation records are backed up, and rollback reuses the original
  activation canary rather than fabricating new evidence.

## Formal provider-path replay

The accepted 15-document, 17-query frozen packet was replayed through
`Qwen3EmbeddingProvider`, `Qwen3RerankerProvider` and the persistent
OpenSSH/JSONL transport. This did not call the earlier benchmark's direct model
inference functions.

| Gate | Observed | Required | Result |
| --- | ---: | ---: | --- |
| Dense recall@3 | 1.0000 | 0.9000 | PASS |
| Hybrid recall@3 | 0.9375 | 0.9000 | PASS |
| Rerank recall@1 | 1.0000 | 0.9000 | PASS |
| Cross-language rerank@1 | 1.0000 | 1.0000 | PASS |
| Historical-experiment rerank@1 | 1.0000 | 1.0000 | PASS |
| Conflict evidence coverage@5 | 1.0000 | 1.0000 | PASS |
| Conflict key detected | true | true | PASS |
| Repeated rankings identical | true | true | PASS |
| Source/conflict metadata preserved | true | true | PASS |

The run made 35 embedding requests and 34 reranking requests in 25.750 seconds.
Embedding and reranking models were loaded sequentially. After the JSONL
sessions closed, the remote host reported no gateway process and no GPU compute
process.

## Validation

| Check | Result |
| --- | --- |
| Qwen runtime, provider and index focused tests | 18 PASS |
| Orchestrator regression after the implementation batch | 129 PASS |
| Local provider result credential scan | PASS |
| Tracked gateway and runner credential scan | PASS |
| Remote gateway credential scan | PASS |
| Remote gateway process after close | 0 |
| Remote GPU compute processes after close | 0 |

The exception path was tightened after review so neither remote exceptions nor
Pydantic validation errors can echo response values. Rollback was also
refactored to recover the previous collection's historical canary rather than
rewriting the current canary under another identity.

## Provenance

- Frozen packet SHA-256: `ea26ded24c29d4908df7d749d46c5bc0c67d7b29eb4acfb9d19510ade438dc70`
- Provider qualification runner SHA-256: `ea55f59d46ab6ef2f191e8c5d265159f9d503cc891ef37db06a32ea7270e51d8`
- Isolated gateway SHA-256: `da798fe589d82acff786f684199db10ef91da6d2e751285722d89a8cb51f4797`
- Qualification result SHA-256: `b01ccf479b63d2b73495242fa4de6858f5402f323f91b6b46fd6326386c625dd`

The ignored result JSON remains the authoritative detailed evidence. This
tracked report records only its credential-safe measurements and hashes.

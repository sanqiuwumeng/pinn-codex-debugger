# Qwen3 Retrieval Model Gate Proposal

- Date checked: 2026-07-16
- Status: runtime, immutable model downloads and formal remote BF16 benchmark approved and complete
- Dense model fixed by user: `Qwen/Qwen3-Embedding-8B`
- First reranker benchmark fixed by user: `Qwen/Qwen3-Reranker-4B`

## Official model facts

| Model | Immutable revision observed | Repository bytes | GiB | License |
| --- | --- | ---: | ---: | --- |
| `Qwen/Qwen3-Embedding-8B` | `1d8ad4ca9b3dd8059ad90a75d4983776a23d44af` | 15,150,575,778 | 14.110 | Apache-2.0 |
| `Qwen/Qwen3-Reranker-0.6B` | `e61197ed45024b0ed8a2d74b80b4d909f1255473` | 1,207,488,344 | 1.125 | Apache-2.0 |
| `Qwen/Qwen3-Reranker-4B` | `22e683669bc0f0bd69640a1354a6d0aebcfeede5` | 8,059,548,421 | 7.506 | Apache-2.0 |
| `Qwen/Qwen3-Reranker-8B` | `77d193c791ed757ca307ee72715aa132723da912` | 16,393,071,729 | 15.267 | Apache-2.0 |

Sizes and revisions were read from the official Hugging Face model API with
blob metadata. They are observations for an immutable download plan, not a
download authorization.

The official model cards describe 32K context and 100+ language support. The
8B embedding model emits up to 4096 dimensions with MRL dimension selection.
Both official model cards require `transformers>=4.51.0`; the embedding card
also states `sentence-transformers>=2.7.0`. The reranker supports either
`sentence-transformers.CrossEncoder` or direct Transformers inference.

## Approved isolation boundary

The user approved the third, physically isolated environment on 2026-07-16:

```text
pinn_strategy_orchestrator   orchestration, Qdrant client, governance
pytorch2.3.1                 existing PINN training; never mutated by RAG
pinn_strategy_retrieval_models  Qwen model runtime and weights
```

The orchestration environment should call the model runtime through an
explicit versioned provider adapter. PyTorch, Transformers and model weights
should not be installed into `pinn_strategy_orchestrator`, and retrieval
packages should not be added to `pytorch2.3.1`.

`pinn_strategy_retrieval_models` now contains the approved Python 3.11.11
runtime pins. `pip check`, CUDA allocation and model-free import checks report
no failures. The existing orchestration and PINN training environments were
not modified.

## Measured workstation boundary

| Resource | Measured value |
| --- | --- |
| GPU | NVIDIA GeForce RTX 5070, compute capability 12.0 |
| Driver | 596.49 |
| GPU memory | 12,227 MiB |
| Physical memory | 31.81 GiB |
| Free disk | C: 316.61 GiB; E: 414.83 GiB |
| Existing PINN PyTorch | 2.3.1 CPU-only; `torch.version.cuda is None` |

The official embedding repository is 14.110 GiB before runtime overhead, so
Qwen3-Embedding-8B BF16 cannot be treated as a local full-precision GPU path.
The existing PyTorch 2.3.1 environment also cannot drive this Blackwell GPU.

## Adjusted two-lane execution plan

| Lane | Purpose | Precision and loading | Initial workload | Result authority |
| --- | --- | --- | --- | --- |
| Local qualification | Adapter, CUDA, memory and end-to-end integration checks | Official revisions, 8-bit first, sequential model loading | batch 1, at most 1024 tokens, one model resident | Feasibility evidence only |
| Formal benchmark | Retrieval quality, latency and acceptance decision | Official revisions, BF16, sequential model loading | frozen benchmark; initial cap 2048 tokens | Quality baseline |

Local execution SHALL unload the embedding model and verify released CUDA
allocations before loading the reranker. If 8-bit loading exceeds the local
memory gate, 4-bit may be evaluated only as a separately labelled fallback;
it SHALL NOT replace the BF16 formal quality baseline. A 32K context claim is
model capability metadata, not an approved initial benchmark setting.

The formal lane should use at least 24 GiB GPU memory for batch-1 bounded-context
qualification; 48 GiB is preferred for longer-context or concurrent work. Any
remote GPU, hosted service or model transfer remains separately approval-gated.

## Resolver-only package proposal

Before installation approval, the empty sandbox successfully resolved this
Windows Blackwell-compatible stack without installing it:

```text
torch==2.12.1+cu130
transformers==4.57.6
sentence-transformers==5.6.0
accelerate==1.14.0
bitsandbytes==0.49.2
huggingface-hub==0.36.2
safetensors==0.8.0
```

PyTorch 2.12.1 is selected instead of the week-old 2.13.0 feature release to
reduce first-benchmark churn while retaining CUDA 13.0 Blackwell support.
Transformers remains on the mature 4.x line instead of taking the 5.x major
upgrade into the first benchmark. The official Qwen cards require
`transformers>=4.51.0`; the embedding card also requires
`sentence-transformers>=2.7.0`. Current bitsandbytes Windows CUDA 12.8-12.9
and 13.0 wheels include the `sm120` target.

Primary references:

- https://pytorch.org/blog/pytorch-2-12-release-blog/
- https://pytorch.org/get-started/previous-versions/
- https://huggingface.co/Qwen/Qwen3-Embedding-8B
- https://huggingface.co/Qwen/Qwen3-Reranker-4B
- https://huggingface.co/docs/bitsandbytes/installation

## Required gates

1. Runtime isolation and the first 4B reranker specification are approved.
2. The empty sandbox, hardware record and resolver-only dependency check are complete.
3. Obtain explicit approval for the seven top-level runtime package pins.
4. After installation, pass imports, `pip check`, CUDA capability and a synthetic
   no-model allocation check.
5. Obtain separate model-download approval for the exact immutable revisions.
6. Run local qualification without granting it formal quality authority.
7. Obtain separate approval for a formal remote benchmark if local BF16 cannot run.
8. Run the frozen multilingual, code, historical-report, conflict and latency
   benchmark before task 5.2 or 5.6 is closed.

## Recorded gate outcome

All eight gates are complete. The seven exact runtime packages were installed
in the isolated Python 3.11.11 model environment, the two approved immutable
model revisions were downloaded on the approved remote GPU instance, and the
formal BF16 benchmark completed on 2026-07-16.

The uniform six-candidate baseline exposed a conflict-recall failure caused by
an uninformative lexical ranking pushing one dense top-2 conflict document out
of the reranker pool. A globally expanded ten-candidate diagnostic passed. The
accepted first-principles policy keeps six candidates for ordinary queries and
uses ten only for `mode=all` conflict/all-evidence queries. The final run passed
all quality gates with 106 pairs, preserved deterministic rankings, and
released all process GPU memory.

The selected model pair is accepted for isolated provider integration under
that evidence policy. Full measurements, failure provenance, hashes and the
remaining authorization boundaries are recorded in
`validation/benchmarks/qwen3-autodl-formal-benchmark-2026-07-16.md`.

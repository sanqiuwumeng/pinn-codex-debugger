# Qwen3 AutoDL Formal Retrieval Benchmark

- Date: 2026-07-16
- Outcome: **PASS with an evidence-policy correction**
- Authority: formal remote BF16 quality baseline
- Evidence root: `validation/benchmarks/results/autodl-a6000/qwen3_remote_session_20260716T051709Z_verified/`

## Scope and immutable inputs

The benchmark used the approved isolated Python 3.11.11 model runtime and did
not mutate the existing `pytorch2.3.1` training environment or the
`pinn_strategy_orchestrator` environment.

| Role | Model | Immutable revision | Logical bytes |
| --- | --- | --- | ---: |
| Dense embedding | `Qwen/Qwen3-Embedding-8B` | `1d8ad4ca9b3dd8059ad90a75d4983776a23d44af` | 15,150,575,778 |
| Reranking | `Qwen/Qwen3-Reranker-4B` | `22e683669bc0f0bd69640a1354a6d0aebcfeede5` | 8,059,548,421 |

The primary Hugging Face endpoint was unreachable from the instance. The
accessible mirror API returned the exact approved commit SHA for both model
repositories before download. No model or revision substitution occurred.
The successful cache contained no residual `.incomplete` files.

The frozen packet contains 15 sanitized/synthetic documents and 17 queries
covering the existing families, paraphrase, Chinese/English cross-language
retrieval, code and unit semantics, metric priority plus localized `max_abs`,
historical metric trade-offs, conflicting evidence and index provenance. It
contains no user training source, raw dataset, output artifact or credential.

## Execution environment

| Item | Measured value |
| --- | --- |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition |
| GPU memory | 97,887 MiB |
| Compute capability | 12.0 |
| Driver | 590.44.01 |
| Python | 3.11.11 |
| PyTorch / CUDA runtime | 2.12.1+cu130 / 13.0 |
| Transformers | 4.57.6 |
| Sentence Transformers | 5.6.0 |
| Precision / attention | BF16 / SDPA |
| Maximum input length | 2,048 tokens |

## Debug to decision trace

The failed attempts are preserved because they materially changed the accepted
retrieval policy.

| Run | Result | Finding |
| --- | --- | --- |
| Initial formal launch | Execution FAIL | PyTorch peak-memory reset was called before CUDA context initialization. The runner was refactored to initialize CUDA explicitly and a regression test was added. |
| Corrected uniform `k=6` baseline | Scientific FAIL | Dense ranked the two conflict documents 1/2, but an equal-weight zero-signal lexical ranking pushed them to hybrid ranks 5/8. Only one entered the six-document reranker pool, so conflict coverage was 0.5. |
| Uniform `k=10` diagnostic | PASS | Both conflict documents entered reranking and were ranked 1/2, proving that the selected models can solve the case. Pair count rose from 102 to 170. |
| Adaptive `k=6/10` confirmation | **PASS** | Single-evidence cases retained six candidates; only `mode=all` used ten. All gates passed with 106 pairs. |

This is an evidence-policy correction, not a relaxed quality threshold. The
packet, model revisions, BF16 precision, token cap and all eight acceptance
thresholds remained unchanged.

## Final quality result

| Stage or gate | Observed | Threshold | Result |
| --- | ---: | ---: | --- |
| Dense recall@3 | 1.0000 | 0.9000 | PASS |
| Hybrid recall@3 | 0.9375 | 0.9000 | PASS |
| Rerank recall@1 | 1.0000 | 0.9000 | PASS |
| Cross-language rerank@1 | 1.0000 | 1.0000 | PASS |
| Historical-experiment rerank@1 | 1.0000 | 1.0000 | PASS |
| Conflict evidence coverage@5 | 1.0000 | 1.0000 | PASS |
| Conflict key detected | `radiation_temperature_unit = [K, degC]` | required | PASS |
| Repeated rankings identical | true; maximum reranker score delta 0.0 | required | PASS |

The final reranker metrics were recall@1 1.0000, recall@3 1.0000 and MRR
1.0000. The two conflicting temperature documents ranked first and second.

The deterministic lexical baseline was substantially weaker
(recall@1/recall@3/MRR = 0.4375/0.5625/0.5601), and equal-weight RRF reduced
dense top-rank quality. Therefore the lexical channel must remain a recall aid,
not an authority that can suppress dense conflict evidence when it has no
query signal.

## Resource result

| Component | Load seconds | Two-pass work seconds | Peak allocated MiB | Allocated after release MiB |
| --- | ---: | ---: | ---: | ---: |
| Qwen3 Embedding 8B | 3.618 | 1.107 | 14,518.280 | 32.000 |
| Qwen3 Reranker 4B | 1.982 | 2.222 | 8,161.484 | 32.000 |

Models were loaded sequentially. After the process exited, `nvidia-smi`
reported 0 MiB used and 0% utilization. The final adaptive policy scored 106
query-document pairs rather than the 170 pairs required by global expansion.

## Acceptance decision

`Qwen3-Embedding-8B` and `Qwen3-Reranker-4B` are accepted for the isolated
retrieval-provider implementation under these mandatory constraints:

1. Load only the approved immutable revisions through an explicit provider.
2. Keep model runtime and weights outside the orchestration and training
   environments.
3. Use at least six rerank candidates for single-evidence queries and ten for
   conflict or all-evidence queries.
4. Run conflict detection before an Agent is allowed to treat retrieved
   evidence as decision-safe.
5. Do not allow an uninformative lexical channel or a single reranked document
   to erase contradictory dense evidence.
6. Preserve model, packet, runner, result and environment provenance for every
   accepted benchmark or future provider revision.

This decision does not authorize hosted model services, production Qdrant,
full PINN training or general deep-learning automation.

## Provenance

- Frozen packet SHA-256: `ea26ded24c29d4908df7d749d46c5bc0c67d7b29eb4acfb9d19510ade438dc70`
- Accepted runner SHA-256: `05aeee44f295347b7dec5cd393059e1a89222a80fb0774b99a75b0f9fe0e9990`
- Final result SHA-256: `91a6e211559b64be92be08d2cb66e4e7e5a09ab3ffb3300fea3ff4a44f41bdbe`
- Evidence archive SHA-256: `8876959ac676a192776b69dc01aba843831c902cb5f2354791ea08d112c6163d`
- Evidence manifest: `run_logs/qwen3_session_evidence_sha256_20260716T0601Z.txt`
- Authoritative final result: `results/qwen3_retrieval_benchmark_20260716T060041Z/benchmark-result.json`

The first direct directory transfer was interrupted after a partial copy. It
was preserved as non-authoritative transfer evidence. Only the `_verified`
evidence root above passed the archive and 33-entry file-level SHA-256 checks.

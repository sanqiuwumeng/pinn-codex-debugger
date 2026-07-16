# Qwen Runtime Dependency Installation

- Date: 2026-07-16
- Target: `C:\Users\Mli\.conda\envs\pinn_strategy_retrieval_models\python.exe`
- Status: package installation and no-model GPU validation passed
- Model download status: blocked and not attempted

This report supersedes only the runtime-state wording in
`qwen3-model-gate-proposal-2026-07-16.md`. The model identifiers, immutable
revision proposal, two-lane execution plan and model-download gate remain in
force.

## Installed top-level pins

```text
torch==2.12.1+cu130
transformers==4.57.6
sentence-transformers==5.6.0
accelerate==1.14.0
bitsandbytes==0.49.2
huggingface-hub==0.36.2
safetensors==0.8.0
```

The install used the official PyTorch CUDA 13.0 wheel index plus PyPI and
completed with exit code 0. The resolver-selected transitive dependencies are
preserved in `retrieval-model-environment-freeze-2026-07-16.txt`.

## No-model validation

Offline flags were set before importing the runtime libraries. No
`from_pretrained` call was made.

| Check | Result |
| --- | --- |
| `pip check` | pass; no broken requirements |
| CUDA available | `true` |
| CUDA runtime | 13.0 |
| GPU | NVIDIA GeForce RTX 5070 |
| Compute capability | 12.0 |
| Compiled architecture | `sm_120` present |
| Synthetic GPU operation | pass |
| bitsandbytes NF4 quantize/dequantize | pass |
| NF4 reconstruction MAE | 0.07275390625 on synthetic FP16 tensor |
| Peak allocated memory | 12.378 MiB |
| Post-cleanup allocated/reserved | 0.0 / 0.0 MiB |

PyTorch emitted a non-blocking `triton not found` warning from its FLOP-counter
module. No additional Triton dependency was added: eager CUDA and bitsandbytes
kernels passed, while FLOP counting is outside the approved model-runtime
scope.

## Isolation and regression

- Existing `pytorch2.3.1` remains PyTorch 2.3.1 with no CUDA runtime.
- Existing `pinn_strategy_orchestrator` remains LangGraph 1.2.9 and FastEmbed 0.8.0.
- The Hugging Face hub cache directory did not exist after validation.
- 82 orchestration `unittest` cases passed.
- 20 MCP `unittest` cases passed.
- Orchestrator source `compileall` passed.
- `git diff --check` passed.
- strict OpenSpec validation passed.

## Closed-loop review

1. Debug: corrected the test runner from an unavailable `pytest` command to
   the repository's declared `unittest` framework, then fixed MCP package
   discovery with `-t .`.
2. First-principles refactoring: kept validation tied to explicit interpreters,
   explicit source roots and offline model-library imports.
3. Simplification: did not add pytest, Triton, a model server or another
   environment because none is necessary for the approved runtime gate.

## Remaining gate

No Qwen tokenizer, configuration or weight may be downloaded until the user
separately approves the exact repositories, immutable revisions and cache
location. Local qualification and the formal AutoDL benchmark remain separate
execution approvals.

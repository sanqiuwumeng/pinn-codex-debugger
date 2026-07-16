# Qwen Runtime Resolver Plan

- Date: 2026-07-16
- Target: `pinn_strategy_retrieval_models`
- Status: resolver-only check passed; installation not approved and not performed

## Proposed top-level pins

| Package | Pin | Reason |
| --- | --- | --- |
| PyTorch | `torch==2.12.1+cu130` | CUDA 13.0 Blackwell wheel; maintenance release rather than week-old 2.13.0 |
| Transformers | `transformers==4.57.6` | Qwen3 support while avoiding a first-benchmark 5.x major upgrade |
| Sentence Transformers | `sentence-transformers==5.6.0` | Embedding and CrossEncoder adapters |
| Accelerate | `accelerate==1.14.0` | Explicit device mapping and controlled CPU offload |
| bitsandbytes | `bitsandbytes==0.49.2` | Windows `sm120` 8-bit/4-bit qualification path |
| Hugging Face Hub | `huggingface-hub==0.36.2` | Resolved 4.x Transformers-compatible Hub client |
| Safetensors | `safetensors==0.8.0` | Explicit safe weight format runtime |

## Resolver result

`pip install --dry-run --ignore-installed --only-binary=:all:` completed with
exit code 0 using the official PyTorch CUDA 13.0 index plus PyPI. It selected:

```text
torch-2.12.1+cu130
transformers-4.57.6
sentence-transformers-5.6.0
accelerate-1.14.0
bitsandbytes-0.49.2
huggingface_hub-0.36.2
safetensors-0.8.0
tokenizers-0.22.2
numpy-2.4.6
scipy-1.17.1
scikit-learn-1.9.0
```

The remaining transitive packages were also resolvable. The dry run fetched
metadata only; it did not install wheels or download model weights.

## Post-install gates

Package installation, if separately approved, must stop after:

1. `pip check` and exact version imports;
2. `torch.cuda.is_available()` and compute capability 12.0 verification;
3. bitsandbytes CUDA backend import and `sm120` kernel availability check;
4. a small synthetic tensor allocation with peak-memory evidence;
5. full environment freeze and regression tests.

No model repository may be opened by `from_pretrained` during this dependency
stage. Model downloads require a later explicit approval tied to immutable
revisions and cache paths.

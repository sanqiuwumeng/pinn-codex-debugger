# Qwen Runtime Dependency Approval

- Date: 2026-07-16
- User response: `Yes`
- Target environment: `pinn_strategy_retrieval_models`

## Approved top-level packages

```text
torch==2.12.1+cu130
transformers==4.57.6
sentence-transformers==5.6.0
accelerate==1.14.0
bitsandbytes==0.49.2
huggingface-hub==0.36.2
safetensors==0.8.0
```

## Approval boundary

This approval authorizes installing the seven exact top-level pins and their
resolver-selected transitive dependencies into the independent retrieval-model
sandbox. It also authorizes package imports, `pip check`, CUDA capability
inspection, bitsandbytes backend inspection and a small synthetic GPU tensor
allocation.

It does not authorize:

- opening any model repository with `from_pretrained`;
- downloading Qwen model configuration, tokenizer or weights;
- connecting to AutoDL or transferring project/model data;
- running retrieval-quality, PINN smoke or formal model benchmarks;
- modifying `pytorch2.3.1` or `pinn_strategy_orchestrator`.

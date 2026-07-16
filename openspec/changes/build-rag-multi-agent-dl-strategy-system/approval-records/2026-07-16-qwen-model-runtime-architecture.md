# Qwen Model Runtime Architecture Approval

- Date: 2026-07-16
- User response: `Yes`
- Approved sandbox: `pinn_strategy_retrieval_models`
- Approved first reranker benchmark specification: `Qwen3-Reranker-4B`

## Approval Boundary

This approval authorizes creation of an independent Python 3.11.11 conda sandbox for retrieval-model runtime isolation and fixes Qwen3-Reranker-4B as the first reranker benchmark specification.

It does not authorize:

- installing PyTorch, Transformers, Sentence Transformers, quantization, or model-serving packages;
- downloading Qwen3-Embedding-8B or Qwen3-Reranker-4B model weights;
- executing a real-model benchmark or PINN smoke experiment;
- treating unresolved physical-unit declarations as confirmed;
- selecting the user's metric priority or MAE acceptance threshold.

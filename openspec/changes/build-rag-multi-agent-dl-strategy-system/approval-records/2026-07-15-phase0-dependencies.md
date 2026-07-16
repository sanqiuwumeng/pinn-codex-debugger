# Phase 0 Dependency Approval Record

- **Date:** 2026-07-15
- **Change:** `build-rag-multi-agent-dl-strategy-system`
- **User approval:** `Approve Phase 0 dependencies`
- **Environment:** `C:\Users\Mli\.conda\envs\pinn_strategy_orchestrator`
- **Authorized packages:** Exact Phase 0 pins in `dependency-plan.md`
- **Not authorized:** Phase 1 packages, embedding/reranking model downloads, production services and full training

## Recorded Future Model Choice

- Dense embedding model family: `Qwen3-Embedding-8B`
- Reranker model family: `Qwen3 Reranker`

The model-family choice is recorded for later design work. It does not authorize downloading weights, selecting an unconfirmed reranker size/revision, or installing a model runtime.

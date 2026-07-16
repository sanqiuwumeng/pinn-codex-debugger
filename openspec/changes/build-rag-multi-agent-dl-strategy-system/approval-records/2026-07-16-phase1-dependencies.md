# Phase 1 Dependency Approval Record

- **Date:** 2026-07-16
- **Change:** `build-rag-multi-agent-dl-strategy-system`
- **User approval:** `Approve Phase 1 package dependencies`
- **Target environment:** `C:\Users\Mli\.conda\envs\pinn_strategy_orchestrator`

## Approved package pins

- `mlflow==3.14.0`
- `qdrant-client==1.18.0`
- `fastembed==0.8.0`
- `psutil==7.2.2`

## Boundaries retained

- The existing `pytorch2.3.1` training environment is not modified.
- Package installation does not authorize downloading Qwen3 model weights.
- No standalone Qdrant server, hosted MLflow, Docker service, remote runner,
  training run or smoke experiment is authorized by this approval.
- Qwen3-Embedding-8B and Qwen3 Reranker remain behind the model-specific
  resource, revision and download gate.

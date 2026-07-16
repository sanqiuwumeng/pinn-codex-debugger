# Phase 2 Dependency Plan

## Decision

首批 Phase 2 实现不新增 Python 包，也不修改现有环境。

| Concern | Selected implementation | Environment |
| --- | --- | --- |
| CLI | Python standard-library argument parsing | `pinn_strategy_orchestrator` |
| Local execution | `subprocess`, PowerShell process/status files, `psutil` already pinned | orchestrator/host |
| AutoDL transport | Windows system `ssh.exe` and `scp.exe` with approved key | host |
| Workflow | existing LangGraph and SQLite checkpointer | `pinn_strategy_orchestrator` |
| Vector index | existing `qdrant-client==1.18.0` local mode | `pinn_strategy_orchestrator` |
| Model client transport | versioned JSONL request/response over an injected transport | orchestrator |
| Qwen3 runtime | already validated isolated Transformers/SentenceTransformers runtime | isolated model environment |
| PINN training | case-locked Python/PyTorch environment | separate training environment |

## Mandatory isolation

- Qwen3 packages and weights SHALL NOT be installed into `pinn_strategy_orchestrator` or `pytorch2.3.1`.
- CLI and Runner changes SHALL NOT mutate the training environment.
- SSH credentials SHALL NOT enter a Python dependency, repository file or serialized workflow object.
- If implementation later requires a new package, the relevant task pauses until a new dry-run, version pin, environment manifest and explicit dependency approval are recorded.

## Accepted immutable retrieval models

- Embedding: `Qwen/Qwen3-Embedding-8B` at `1d8ad4ca9b3dd8059ad90a75d4983776a23d44af`.
- Reranker: `Qwen/Qwen3-Reranker-4B` at `22e683669bc0f0bd69640a1354a6d0aebcfeede5`.

No hosted inference API or model substitution is authorized by this plan.

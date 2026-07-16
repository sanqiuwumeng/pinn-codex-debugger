# Orchestrator Dependency and Deployment Plan

- **Status:** Phase 0 and Phase 1 packages installed and verified; model downloads pending
- **Date:** 2026-07-16
- **Target change:** `build-rag-multi-agent-dl-strategy-system`
- **Architecture approval:** User replied `Yes` on 2026-07-15
- **Environment decision:** Dedicated orchestration sandbox
- **Phase 0 dependency approval:** User replied `Approve Phase 0 dependencies` on 2026-07-15
- **Phase 1 dependency approval:** User replied `Approve Phase 1 package dependencies` on 2026-07-16

## Environment Boundary

### Orchestration environment

```text
Name: pinn_strategy_orchestrator
Path: C:\Users\Mli\.conda\envs\pinn_strategy_orchestrator
Python: 3.11.15
Purpose: LangGraph orchestration, deterministic audits, RAG indexing,
         experiment tracking adapters and process supervision
```

The approved Phase 0 packages were installed and verified on 2026-07-15. The
approved Phase 1 packages were installed and verified on 2026-07-16. The
complete manifests and resolver evidence are stored under
`validation/dependencies/`. No vector model or external service has been
installed.

### Training environment

```text
Name: pytorch2.3.1
Path: C:\Users\Mli\.conda\envs\pytorch2.3.1
Purpose: Existing PINN training and numerical experiment execution
```

The orchestration environment SHALL invoke the training environment only through an explicit runner adapter and `RunManifest`. It SHALL NOT import the training environment's site-packages or mutate that environment.

## Installation Gates

Dependencies are divided into separately approved stages. Approval of one stage does not approve later stages or model downloads.

1. **Phase 0 core packages:** required for schemas, read-only graph, SQLite persistence, unit audit and deterministic field analysis.
2. **Phase 1 service packages:** required for local experiment tracking, vector storage and process monitoring.
3. **Embedding/reranking models:** binary model downloads selected only after a small benchmark and license/resource review.
4. **Production services:** PostgreSQL, remote Qdrant, object storage, remote runners and hosted observability remain out of scope until a later approval.

## Phase 0 Core Packages

| Package | Proposed pin | Purpose | Rationale |
| --- | ---: | --- | --- |
| `langgraph` | `1.2.9` | Explicit workflow graph, interrupts and state transitions | Current PyPI version observed on 2026-07-15 |
| `langgraph-checkpoint-sqlite` | `3.1.0` | Local durable checkpoints and replay | Official local-development checkpointer |
| `pydantic` | `2.13.4` | Versioned explicit data contracts | Strict validation and JSON serialization |
| `pint` | `0.25.3` | Deterministic unit parsing and conversion | Prevent LLM-authored conversion arithmetic |
| `numpy` | `2.4.6` | Field metrics, alignment and array operations | Deterministic numerical core |
| `scipy` | `1.17.1` | Connected hotspots and approved interpolation utilities | Avoid custom connected-component code |

Phase 0 SHALL use standard-library `unittest`; no additional test framework is required.

### Phase 0 acceptance criteria

- All versioned domain contracts validate and serialize without arbitrary-object or pickle fallback.
- LangGraph exposes the RFC state machine and persisted `NEEDS_*` interrupts.
- Checkpoint/replay tests pass with SQLite.
- Unit and dimensional audit fixtures pass without changing source configuration.
- Metric preference blocks decision when required user priorities are absent.
- Prediction analysis returns `max_abs` location, top-k points, connected regions and time-slice evidence on synthetic fixtures.
- Existing `pinn-hybrid-rag` is accessed through an explicit read-only adapter.
- No PINN source file is modified and no training process is started.

## Phase 1 Service Packages

| Package | Proposed pin | Purpose | Installation boundary |
| --- | ---: | --- | --- |
| `mlflow` | `3.14.0` | Local experiment/run/metric metadata and artifact references | Install only after Phase 0 passes |
| `qdrant-client` | `1.18.0` | Local-mode vector index and future remote adapter | No server or collection before store tests |
| `fastembed` | `0.8.0` | Lightweight ONNX embedding/reranking provider | Package install does not authorize model download |
| `psutil` | `7.2.2` | Deterministic local process/resource events | Monitor only approved processes |

### Phase 1 development deployment

```text
LangGraph checkpoints: project-local SQLite under an ignored runtime root
MLflow backend: project-local SQLite
MLflow artifacts: project-local artifact directory
Qdrant: local mode with a project-local persistence directory
Audit events: SQLite append-only table
Wiki and Skill source: Git-managed Markdown/JSON candidates
```

Every runtime directory SHALL be added to `.gitignore` only after the existing file is backed up. Runtime data SHALL not be placed inside package source directories.

### Phase 1 acceptance criteria

- Workflow, MLflow and vector storage have distinct ownership and paths.
- A run manifest, metric record and artifact reference survive process restart.
- The vector collection can be deleted and rebuilt from authoritative source documents.
- Current deterministic retrieval remains available when vector retrieval is disabled.
- Metadata-first filtering and evidence provenance are covered by tests.
- No embedding model is downloaded without model-specific approval.
- Only an explicitly approved smoke command can be launched through the runner adapter.

## Embedding and Reranking Model Gate

The user selected the following future model families on 2026-07-15:

```text
Dense embedding: Qwen3-Embedding-8B
Reranking: Qwen3 Reranker
```

This records the architectural model choice but does not authorize a model download. The exact reranker repository/parameter size, immutable revisions, runtime backend and resource plan remain to be confirmed. After Phase 1 packages are installed, the implementation SHALL verify backend compatibility and create a benchmark packet containing:

- model identifier and immutable revision when available;
- license and allowed usage;
- download size and on-disk footprint;
- embedding dimension and maximum input length;
- Chinese, English and mixed technical-query behavior;
- CPU latency and peak memory in the orchestration environment;
- frozen nine-family retrieval result;
- paraphrase, cross-language, code-map and evidence-conflict result;
- comparison against the current deterministic retriever.

The first model download requires a separate explicit approval. The benchmark SHALL use the selected Qwen3 model families and SHALL NOT silently substitute a smaller or unrelated model.

## Explicitly Deferred Dependencies and Services

The following are not approved by this plan:

- `langgraph-checkpoint-postgres` or a PostgreSQL server;
- Docker or a standalone Qdrant server;
- MinIO, S3 or other remote artifact stores;
- LangSmith or any hosted tracing service;
- Redis, MongoDB or message queues;
- cloud embedding or LLM APIs;
- Optuna/ASHA or other optimization engines;
- AutoDL, WSL or other remote execution adapters;
- CUDA, PyTorch or training packages inside the orchestration environment.

Each deferred item requires a later design/dependency update and explicit approval.

## Recorded Phase 0 Installation

The approved top-level pins were installed with the exact orchestration interpreter.
`pip check`, package imports and the 20-test legacy MCP regression suite passed.
The resolver dry-run, environment manifest and complete `pip freeze` are preserved in
`validation/dependencies/`.

## Recorded Phase 1 Installation

The four approved Phase 1 top-level pins were installed with the exact
orchestration interpreter on 2026-07-16. `pip check`, imports, 82 orchestrator
tests, 20 legacy MCP tests and strict OpenSpec validation passed. Resolver,
installation, environment and freeze evidence are preserved under
`validation/dependencies/`.

The separately approved `pinn_strategy_retrieval_models` runtime was installed
without mutating the orchestration or `pytorch2.3.1` training environments.
The exact approved Qwen3 revisions were downloaded only on the approved remote
GPU instance, and the formal BF16 benchmark completed on 2026-07-16. No hosted
service, training process or PINN smoke experiment was started.

FastEmbed 0.8.0 compatibility inspection found no Qwen entry in its 30-model
dense embedding catalog or its 6-model cross-encoder catalog. Therefore
FastEmbed remains only an approved package boundary; it is not the runtime for
Qwen3-Embedding-8B or Qwen3 Reranker. The accepted runtime is the isolated
PyTorch/Transformers provider recorded in
`validation/benchmarks/qwen3-autodl-formal-benchmark-2026-07-16.md`.

## Installation Procedure After Approval

1. Verify the target interpreter is exactly:

   ```text
   C:\Users\Mli\.conda\envs\pinn_strategy_orchestrator\python.exe
   ```

2. Run a resolver-only dry run for the approved stage and preserve its report.
3. Install exact top-level pins with that interpreter; do not use an activated ambiguous shell.
4. Run `python -m pip check`.
5. Record `pip freeze`, Python version, platform and package import versions in an environment manifest.
6. Run import smoke tests and the existing product regression suite.
7. Do not install the next stage until the current stage's acceptance criteria pass.

## Rollback and Data Safety

- Package failure SHALL preserve resolver and installation logs.
- The training environment SHALL remain untouched.
- No automatic environment deletion is authorized.
- If the orchestration environment is rejected, removal requires a separate explicit user request.
- Existing project files SHALL be backed up before modification.
- Runtime databases, indexes and artifacts SHALL not be deleted as a rollback mechanism.

## Version Evidence

Proposed pins were verified through the environment's `pip index versions` command on 2026-07-15. Architecture choices also follow the official LangGraph SQLite checkpointer, Qdrant FastEmbed and MLflow local SQLite guidance:

- https://docs.langchain.com/oss/python/integrations/checkpointers/index
- https://qdrant.tech/documentation/fastembed/
- https://mlflow.org/docs/latest/self-hosting/architecture/overview/

## Remaining Required Approvals

Phase 0, Phase 1, the isolated Qwen3 runtime, the exact model downloads and the
formal remote benchmark are approved and complete. The selected models passed
under an adaptive evidence policy of six ordinary candidates and ten
all-evidence/conflict candidates. Production services, PINN smoke execution,
full runs and general deep-learning automation remain separately gated.

# Portable qualification workflows

This directory contains release-facing verification tools, not development
history or stored experiment evidence.

- `poisson/` runs the manufactured two-dimensional Poisson PINN case.
- `burgers/` builds and verifies a numerical reference, then runs the viscous
  Burgers PINN case across the frozen seed set.
- `qwen/` downloads and qualifies the pinned Qwen3 embedding and reranker
  providers against the frozen retrieval contract.
- `backends/` verifies the bounded remote execution backend.
- `remote_e2e/` verifies Wiki publication, Qwen RAG retrieval, governed Poisson
  execution, replay, provenance and completion-bundle integrity.

Poisson and Burgers runners require two caller-owned `ApprovalRecord` JSON
files: one with kind `METRIC_PRIORITY`, and one with kind `EXPERIMENT`. Both
must be `APPROVED` and name the exact workflow identifier:

- Poisson: `poisson-qualification-v1`
- Burgers: `burgers-cross-domain-qualification-v1`
- bounded AutoDL backend: `autodl-backend-qualification-workflow`

Each record's `scope` must equal `qualification:<workflow_id>`. Approval
evidence belongs to each execution packet or result bundle; it is never
embedded in release source.

Run all non-training release gates from the repository root:

```powershell
<orchestration-python> `
  skills\pinn-rag-strategy-system\scripts\run_release_gates.py `
  --repo-root . `
  --python <orchestration-python>
```

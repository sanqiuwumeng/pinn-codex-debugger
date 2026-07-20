# PINN Strategy Orchestrator

This package is the isolated orchestration and assurance runtime for the
three-layer PINN strategy system.

## Layer boundaries

- `execution` contains explicit read-only or manifest-first adapters.
- `orchestration` owns LangGraph state transitions and human interrupts.
- `assurance` owns deterministic physical and metric gates.
- `contracts` is the only data interchange surface between layers.
- `storage` owns explicit local checkpoint, MLflow, artifact and audit paths.
- `retrieval` owns the read-only knowledge source, derived Qdrant index,
  metadata filtering, reciprocal-rank fusion, conflict detection and
  provenance validation.

The package does not import a PINN training environment, mutate PINN source
files, or place arrays, weights, figures, or complete logs in graph state.
Phase 0 is read-only and uses an explicitly supplied SQLite checkpointer.
Phase 1 adds local development persistence and process sampling with explicit
path and process identities. Vector tests inject deterministic embeddings:
they do not instantiate FastEmbed or download Qwen3 model weights.

## Operator call sequence

Use `pinn_strategy_orchestrator` for these commands. The Python 3.11.11 /
PyTorch 2.3.1 training interpreter remains declared in each run manifest and is
launched only by the execution backend.

1. `diagnose` calls the handbook MCP through an isolated stdio process. It is
   read-only and does not create a workflow.
2. `adapt` validates a project root and include-file list, creates a deterministic
   source snapshot, and writes a new `OperatorCase` without overwriting files.
3. `audit` and `plan` run physical/unit checks and LangGraph human gates. Missing
   metric priority, evidence or approval remains a persisted `NEEDS_*` state.
4. `smoke` or `full` launches only an authorized manifest. `status` reconciles
   the process; `collect` runs only after completion and preserves manifests.
5. `evaluate` verifies field hashes and alignment, localizes errors, then applies
   the confirmed `MetricContract`. Its immutable evidence does not publish Wiki
   or Skill entries.
6. A case adapter combines those metrics with process, artifact, source, data,
   environment and reproducibility checks before smoke can be marked valid.

```text
pinn-strategy diagnose --project-id ... --query ... --mcp-profile ...
pinn-strategy adapt    --manifest ... --output ...
pinn-strategy audit    --case ...
pinn-strategy plan     --case ...
pinn-strategy smoke    --workflow ...
pinn-strategy status   --workflow ...
pinn-strategy collect  --workflow ... --destination ...
pinn-strategy evaluate --contract ...
pinn-strategy full     --workflow ...
pinn-strategy replay   --workflow ...
pinn-strategy rag rebuild|query ...
```

All commands require an absolute `--runtime-root`; relative input paths require
an absolute `--base-directory`. Editable templates are under
`examples/universal-pinn/`.

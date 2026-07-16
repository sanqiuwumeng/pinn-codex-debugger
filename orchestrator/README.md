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

# Phase 1 Implementation Validation

- Date: 2026-07-16
- Change: `build-rag-multi-agent-dl-strategy-system`
- Environment: `C:\Users\Mli\.conda\envs\pinn_strategy_orchestrator`
- Training environment: `pytorch2.3.1` remained outside the install target

## Delivered boundaries

- Explicit `StoreLayout` ownership for LangGraph checkpoints, MLflow run
  metadata, artifacts, Qdrant index, append-only audit events and authoritative
  knowledge source.
- No-overwrite JSON artifact store and append-only SQLite audit store.
- MLflow SQLite run manifest, metric and artifact-reference persistence across
  adapter restart, with explicit SQLAlchemy engine disposal for Windows.
- Qdrant local-mode derived index rebuilt only from read-only
  `*.index.json` source documents.
- Metadata-first project/document/validation/model/framework/version/language
  filters before vector ranking.
- Deterministic plus vector reciprocal-rank fusion; deterministic retrieval
  remains available when the vector collection is absent.
- Conflict findings block `decision_safe`; empty evidence is never
  decision-safe.
- Provenance is validated before indexing and again when a Qdrant result is
  accepted, so source mutation invalidates stale derived evidence.
- Vector collection deletion/rebuild leaves knowledge source and experiment
  artifact files untouched.
- Skill publication requires repeated validated runs, an independent isolated
  replay, accepted baseline comparison and candidate-scoped human
  `SKILL_PROMOTION` approval.
- Psutil sampling is read-only and restricted to an explicit
  run/PID/create-time/approval identity; PID reuse is rejected.

## Closed-loop corrections

1. Corrected MCP unittest discovery to preserve the `tests` package context.
2. Added explicit MLflow engine disposal after Windows exposed a SQLite lock.
3. Moved the Qdrant adapter from generic storage into the retrieval module to
   remove a circular dependency and preserve physical layer isolation.
4. Changed Qdrant local upsert input from tuple to its required list form.
5. Closed local collection storage before Qdrant delete/recreate to avoid a
   Windows SQLite handle leak in qdrant-client 1.18.0.
6. Revalidated authoritative provenance at query time and blocked empty
   retrieval responses from decision use.
7. Removed a test-only validation bypass and constructed valid replay reports
   only through the production governance service.

## Verification

- `python -m compileall -q orchestrator/src`: passed.
- `python -m pip check`: no broken requirements.
- Orchestrator: 82 tests passed.
- Existing MCP product: 20 tests passed.
- `openspec validate build-rag-multi-agent-dl-strategy-system --strict`:
  passed.
- No global/nonlocal business transport, mutable module-level state, implicit
  working directory, PINN training import or MCP implementation import was
  detected by architecture tests.

## Scope retained

- No Qwen3 model object or model weight was downloaded.
- No standalone Qdrant, MLflow server, Docker service or hosted tracing was
  started.
- No PINN source file was modified.
- No smoke, full training or remote experiment process was started.
- Tasks 5.2 and 5.6 remain open for the exact Qwen3 backend and real model
  benchmark packet.

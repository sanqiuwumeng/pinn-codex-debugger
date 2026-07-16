## 1. Governance and Implementation Preconditions

- [x] 1.1 Review this RFC and capability specs with the user; record unresolved decisions and accepted MVP scope.
- [x] 1.2 Obtain a fresh explicit user reply of `Yes` before creating architectural runtime files or changing the current MCP product.
- [x] 1.3 Record whether implementation uses the existing `pytorch2.3.1` environment or a dedicated conda sandbox.
- [x] 1.4 Produce and approve a dependency plan covering LangGraph, checkpointer, experiment tracking, vector storage, embedding models and optional execution backends before installation.
- [x] 1.5 Verify the active target is `exp/hybrid-rag`, preserve the current uncommitted tests, and create required dated backups before modifying any existing file.
- [x] 1.6 Freeze Phase 0 and Phase 1 acceptance criteria; defer general deep-learning support until the PINN path passes them.

## 2. Domain Contracts and Graph Skeleton

- [x] 2.1 Define versioned schemas for requests, snapshots, physical parameters, metric contracts, experiment specs, runs, events, reports, decisions, approvals and knowledge candidates.
- [x] 2.2 Define `WorkflowState` using only serializable small values and artifact references.
- [x] 2.3 Implement the LangGraph state machine with explicit `NEEDS_*`, smoke, full-run, invalid-result and completion states.
- [x] 2.4 Implement persistence and replay tests using an approved development checkpointer.
- [x] 2.5 Prove graph nodes do not exchange data through global mutable state, singletons, implicit working directories or hidden Agent memory.

## 3. Physical Model Preflight Audit

- [x] 3.1 Implement parameter extraction with raw value, raw unit, source, load site and use-site provenance.
- [x] 3.2 Implement deterministic unit parsing and canonical conversion without overwriting original configuration.
- [x] 3.3 Implement PDE/BC/IC dimensional consistency checks and semantic checks for absolute temperature, angular frequency and source dimensionality.
- [x] 3.4 Implement conversion-chain tracing that detects missing and duplicate conversions.
- [x] 3.5 Implement normalized-coordinate derivative scaling checks for first-, second- and time-derivative terms.
- [x] 3.6 Implement `NEEDS_UNIT_CONFIRMATION`, `PASS`, `WARN` and `REJECT` outcomes with user interrupts.
- [x] 3.7 Add fixtures covering mass, density, specific heat, length, time, heat flux, volumetric source and Celsius/Kelvin errors.

## 4. Metric Priority and Prediction Diagnostics

- [x] 4.1 Implement an interactive metric-preference step for physical-model authority, optional reference evidence, primary metrics, guardrails, diagnostics, case-dependent ROI/time windows and thresholds.
- [x] 4.2 Prevent optimization when required preferences are missing or when the user has not authorized a scalar aggregation.
- [x] 4.3 Implement deterministic global, time-slice, ROI and physics metric computation.
- [x] 4.4 Implement `max_abs` argmax, top-k locations, percentile error, connected hot regions and temporal location trajectories.
- [x] 4.5 Attach PDE residual, BC/IC status, sampling density, geometry labels and optional domain-provider context to localized errors.
- [x] 4.6 Implement aligned baseline/candidate comparison and reject mismatched reference, grid or time coordinates.
- [x] 4.7 Add tests where average error improves but a user guardrail or local maximum regresses.

## 5. Governed RAG and Evidence Layer

- [x] 5.1 Wrap the existing `pinn-hybrid-rag` MCP product behind an explicit retrieval provider interface without moving orchestration into the MCP server.
- [x] 5.2 Select and approve vector storage, embedding, sparse retrieval, fusion and reranking dependencies.
- [x] 5.3 Define chunking and metadata schemas for handbook, code map, validated experiment reports, Wiki and Skill sources.
- [x] 5.4 Implement metadata-first filtering, deterministic plus vector retrieval, evidence-conflict handling and provenance validation.
- [x] 5.5 Implement index reconstruction from source-of-truth stores.
- [x] 5.6 Preserve the current frozen routing/ranking tests and add paraphrase, cross-language, historical-experiment and conflict benchmarks.

## 6. Experiment Lifecycle and Process Supervision

- [x] 6.1 Implement completeness audit for code, data, environment, seed, baseline, metric contract, budget, output path, checkpoint and rollback.
- [x] 6.2 Implement experiment specifications that declare one logical intervention and unchanged controls.
- [x] 6.3 Implement a runner adapter with RunManifest-first semantics and idempotency keys.
- [x] 6.4 Implement event-driven monitoring for metrics, checkpoints, NaN, OOM, stalled logs, missing artifacts and completion.
- [x] 6.5 Enforce smoke-first and separate full-run approval in graph transitions.
- [x] 6.6 Implement metric, artifact and reproducibility validation before marking a run valid.
- [x] 6.7 Add failure-injection and resume tests proving successful nodes are not repeated and invalid runs cannot be promoted.

## 7. Persistence, Wiki and Skill Governance

- [x] 7.1 Implement approved development stores for checkpoints, run metadata, artifacts, vector index and audit events with strict ownership boundaries.
- [x] 7.2 Implement Wiki entry candidates with run, source, data, environment, metric and audit references.
- [x] 7.3 Implement version, `supersedes`, invalidation and provenance rules for Wiki entries.
- [x] 7.4 Implement SkillCandidate generation only from repeated validated patterns.
- [x] 7.5 Implement isolated replay, baseline comparison and explicit human promotion for Skill publication.
- [x] 7.6 Prove deleting and rebuilding the vector index does not delete source facts, Wiki source or experiment artifacts.

## 8. Closed-Loop Validation and Release Gates

- [x] 8.1 Run the closed-loop process `Debug -> First-Principles Refactoring -> Simplification` for each implementation stage.
- [x] 8.2 Validate architecture boundaries, data contracts, approval gates, no-overwrite behavior and deterministic services.
- [x] 8.3 Complete one read-only PINN case through audit and decision without source modification.
- [x] 8.4 Complete one approved smoke case through monitoring, localized metric analysis and rollback evaluation.
- [x] 8.5 Repeat the smoke case from persisted state and verify provenance and idempotency.
- [x] 8.6 Produce an evidence-backed MVP report before requesting authorization for full-run automation or general deep-learning expansion.

## 9. Universal PINN Core and Domain Isolation

- [x] 9.1 Revise the RFC and capability specs so the product targets general PINN strategy optimization rather than a heat-transfer-specific core.
- [x] 9.2 Define explicit `UnitSystemContract`, `PhysicalModelAuthority` and `ReferenceEvidence` contracts and remove global SI/FEM assumptions.
- [x] 9.3 Resolve every model-canonical parameter unit from the declared model unit system and test accepted converted mixing plus rejected unconverted mixing.
- [x] 9.4 Generalize the metric contract to distinguish physical-model, reference-evidence and baseline evidence and support simultaneous absolute and relative guardrails.
- [x] 9.5 Replace the graph's prediction-only gate with a model-evaluation gate that permits reference-free physical metrics when the user provides no truth field.
- [x] 9.6 Move heat-transfer phase metrics behind an explicit domain-provider interface and prove the generic prediction analyzer contains no thermal semantics.
- [x] 9.7 Extend RAG metadata filtering with PDE family, task type and optional domain-provider scope so strategies are transferred only across compatible cases.
- [x] 9.8 Validate one heat-transfer provider and one non-thermal provider path, then run the complete orchestration and MCP regression suites.

## 10. Authorized Full-Run Qualification

- [x] 10.1 Record the user's standing remote and full-run authorization without persisting credentials or weakening assurance gates.
- [x] 10.2 Freeze an exact comparable Python 3.11.11 / PyTorch 2.3.1 / NumPy 2.2.5 full-run environment without mutating the existing training environment.
- [x] 10.3 Stage the focused-collocation full reproducibility case read-only and persist its approval, source, environment, baseline and run manifests before launch.
- [x] 10.4 Execute the full run under durable monitoring and verify process, checkpoint, log and expected-artifact completion.
- [x] 10.5 Perform whole-field and localized analysis, apply `max_abs -> RMSE` plus the MAE dual guardrail, and execute the rollback decision when required.
- [x] 10.6 Reopen persisted workflow and launch state, resubmit the same manifest, and verify zero relaunch plus end-to-end provenance.
- [x] 10.7 Produce the full-run evidence report and rerun all OpenSpec, orchestration, MCP and architecture-boundary release checks.

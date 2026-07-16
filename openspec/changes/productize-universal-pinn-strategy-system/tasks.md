## 1. Governance and Release Baseline

- [x] 1.1 Record the user's explicit `Yes` for the Phase 2 productization architecture.
- [x] 1.2 Reuse the approved `pinn_strategy_orchestrator` sandbox and freeze a no-new-package first batch.
- [x] 1.3 Inventory every uncommitted path and classify it as source, test, governed evidence, large artifact, derived runtime state, backup or credential-risk data.
- [x] 1.4 Back up every existing file before modifying release metadata or implementation.
- [x] 1.5 Add narrowly scoped ignore rules without deleting local evidence, then generate a tracked evidence manifest for excluded authoritative artifacts.
- [x] 1.6 Run the complete Phase 1 release gates and credential scan, create a selective baseline commit, and record the commit identity.

## 2. Production Execution Contracts

- [x] 2.1 Replace the launch-only `RunnerBackend` with explicit prepare, launch, reconcile, cancel and collect contracts; migrate callers without a compatibility layer.
- [x] 2.2 Extend the run registry for prepared, running, uncertain, cancelling, cancelled, collecting, completed and failed lifecycle states.
- [x] 2.3 Preserve manifest-first idempotency and require reconciliation before retrying any uncertain launch.
- [x] 2.4 Add typed status, cancellation, log-cursor and artifact-collection contracts with schema-version tests.
- [x] 2.5 Prove the execution layer receives every path, environment value and approval explicitly and uses no hidden working-directory or global state.

## 3. Local Process Backend

- [x] 3.1 Implement `LocalProcessRunnerBackend` with absolute staging paths, argument arrays, environment allowlists and durable status/log files.
- [x] 3.2 Validate PID plus process creation identity and reconcile it with status, exit code, heartbeat and required artifacts.
- [x] 3.3 Implement approved process-tree cancellation and idempotent collection with SHA-256 manifests.
- [x] 3.4 Add tests for success, non-zero exit, NaN/OOM event, stale heartbeat, PID reuse, launch timeout, duplicate submit, cancel and interrupted collection.
- [x] 3.5 Move governed smoke/full adapters onto the production local backend and remove duplicated validation-only launch control.

## 4. AutoDL SSH Backend

- [x] 4.1 Implement an explicit connection-profile contract that persists only an alias and host/key fingerprints.
- [x] 4.2 Implement content-addressed staging, remote path confinement, pre-write backups and remote SHA-256 verification using system OpenSSH.
- [x] 4.3 Implement a durable remote launcher with PID, process identity, heartbeat, status, stdout and stderr artifacts.
- [x] 4.4 Implement disconnect-safe reconcile, approved cancel and manifest-first result collection with partial-transfer quarantine.
- [x] 4.5 Run an AutoDL read-only preflight and a bounded backend qualification job, including simulated disconnect/reconnect and zero-relaunch replay.
- [x] 4.6 Verify remote and local logs, manifests and errors contain no credential or direct connection secret.

## 5. Qwen3 Retrieval Providers and Index Governance

- [x] 5.1 Define versioned embedding, reranking, health and error request/response contracts plus an injected `ModelTransport` interface.
- [x] 5.2 Implement isolated subprocess/remote JSONL transports with timeouts, request IDs, size limits and sanitized errors.
- [x] 5.3 Implement `Qwen3EmbeddingProvider` pinned to the accepted 8B revision and validate dimensions, finiteness and provenance.
- [x] 5.4 Implement `Qwen3RerankerProvider` pinned to the accepted 4B revision and preserve source/conflict metadata through ranking.
- [x] 5.5 Enforce adaptive candidate pools of at least 6 for ordinary queries and 10 for conflict/all-evidence queries.
- [x] 5.6 Version Qdrant collections from model/chunk/metadata/source identities and implement build, canary, atomic activation and rollback.
- [x] 5.7 Reproduce the accepted cross-language, historical, conflict and determinism gates through the production provider path.

## 6. Operator CLI

- [x] 6.1 Add the `pinn-strategy` entry point without adding a new package dependency.
- [x] 6.2 Implement `audit` and `plan` from explicit case contracts with persisted `NEEDS_*` outcomes.
- [x] 6.3 Implement `smoke`, `full`, `status` and `replay` as thin application-service clients.
- [x] 6.4 Implement `rag rebuild` and `rag query` with active-index provenance and conflict visibility.
- [x] 6.5 Add versioned `--json` output, stable exit codes, absolute-path normalization and credential-safe errors.
- [x] 6.6 Prove the CLI cannot bypass physical, metric, approval, smoke-first, reproducibility or promotion gates.

## 7. Cross-Domain Scientific Qualification

- [ ] 7.1 Freeze three or more seeds for the existing thermal focused-collocation case while preserving its case-specific `max_abs -> RMSE` and MAE guardrails.
- [ ] 7.2 Report per-seed metrics, localized maxima, failure modes and aggregate uncertainty without hiding rejected seeds.
- [ ] 7.3 Implement a real two-dimensional Poisson PINN case with manufactured analytic reference and a non-thermal domain provider.
- [ ] 7.4 Complete Poisson audit, metric confirmation, baseline diagnosis, single-intervention smoke, full run, localized analysis, replay and provenance validation.
- [ ] 7.5 Prove Poisson contracts and reports contain no implicit temperature, Kelvin, phase, melt-region or FEM-default semantics.
- [ ] 7.6 Compare evidence across cases and create only governed Wiki/Skill candidates supported by repeated validated patterns.

## 8. Closed-Loop Release Qualification

- [ ] 8.1 Apply `Debug -> First-Principles Refactoring -> Simplification` to each implementation batch and remove duplicated validation-only control logic.
- [ ] 8.2 Run orchestrator, MCP, CLI, backend, retrieval, OpenSpec and architecture-boundary suites in their locked environments.
- [ ] 8.3 Run credential, absolute-path, no-global-state, no-thermal-import and artifact-provenance audits.
- [ ] 8.4 Produce a Phase 2 evidence report with baseline commit, environment manifests, model revisions, backend results and scientific boundaries.
- [ ] 8.5 Mark this OpenSpec complete only when every release gate passes and no mandatory work remains.

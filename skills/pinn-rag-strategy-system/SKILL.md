---
name: pinn-rag-strategy-system
description: Audit, configure, run, qualify, and transfer the governed universal PINN RAG strategy system in this repository. Use when adapting a PINN project, checking mixed physical units, collecting user metric priorities, localizing max_abs errors, querying Qwen-backed RAG, supervising smoke or full runs, publishing validated experiment Wiki entries, verifying remote result bundles, or reproducing the workflow on another machine. Do not use for an ungoverned standalone training run.
---

# PINN RAG Strategy System

## Purpose

Operate the repository as a governed three-layer system: the execution layer runs explicit experiment commands, the orchestration layer controls state and approvals, and the assurance layer validates physics, metrics, provenance, replay, and knowledge promotion. Keep training, orchestration, and retrieval runtimes physically isolated.

Read [references/governance-contract.md](references/governance-contract.md) before making a scientific decision. Read [references/portable-operations.md](references/portable-operations.md) before installing dependencies, using a remote machine, or moving a result bundle. Read [references/security-boundary.md](references/security-boundary.md) before executing third-party project code.

## Non-negotiable rules

1. Treat the user's physical model as the scientific authority. A FEM solution is a case-specific validation reference unless the user explicitly promotes it to model authority.
2. Audit unit consistency before training. Detect incompatible mixing such as metre/millimetre or kilogram/gram along raw code paths; do not reject a coherent non-SI model merely for being non-SI.
3. Obtain and persist the user's metric priority before optimization. Do not infer it from MSE, RMSE, a benchmark, or retrieved text.
4. Analyze the prediction field and localize `max_abs` before proposing an intervention. Preserve coordinates, time, channel, top-k points, connected regions, and local physics context when available.
5. Treat RAG output as advisory evidence only. Measured fields plus the approved case contract retain decision authority. Visible evidence conflicts block decision-safe status.
6. Change one logical experiment factor at a time. Require a bounded smoke result before a full run unless the user has already supplied an applicable standing authorization.
7. Never put passwords, tokens, private keys, direct connection strings, or secret-bearing command arguments into repository files, manifests, logs, Wiki entries, or Skill resources.
8. Never overwrite governed evidence. Use new versioned destinations, hash verification, append-only records, and dated backups for existing files.
9. Do not claim universal scientific effectiveness from one case, one seed, a smoke run, or a rejected candidate.

## Workflow

### 1. Establish the execution context

- Locate the system repository by requiring `orchestrator/`, `mcp-server/`, `retrieval-runtime/`, and `qualification/`.
- Identify the target PINN project, training interpreter, orchestration interpreter, retrieval interpreter, output root, and execution backend.
- Keep the Python 3.11 orchestration environment separate from the PyTorch training environment and the GPU retrieval environment.
- Reuse an approved sandbox. If development begins without one, ask whether to create a conda sandbox before modifying files.
- Run `scripts/audit_repository.py --repo-root <system-repo>` before packaging, publishing, or transferring the system.

### 2. Perform read-only diagnosis and adaptation

1. Use the read-only MCP service for fast symptom routing and handbook evidence.
2. Use `pinn-strategy adapt` to generate an explicit project governance case.
3. Inspect unresolved fields rather than guessing them. At minimum resolve physical authority, unit declarations/conversions, metric priority, reference identity, execution profile, and expected artifacts.
4. Run `pinn-strategy audit`. Do not load an execution backend while the workflow remains read-only.

### 3. Gate physics and metric authority

- Stop on missing unit declarations, incompatible additive dimensions, missing or duplicate conversion paths, invalid absolute-temperature use, or an unconfirmed physical model.
- Ask the user for metric ordering before optimization. Persist both the metric contract and its scoped approval.
- Apply lexicographic, Pareto, or another policy only when explicitly approved for the case. The validated Poisson example uses `max_abs -> RMSE`; the `MAE <= 1.0 K and <= 10% regression` guardrail is temperature-specific and must not be generalized to nonthermal fields.

### 4. Retrieve evidence without delegating authority

- Run deterministic MCP retrieval first when the symptom is known.
- Rebuild the Qwen index only from validated, hash-anchored knowledge documents.
- Use the pinned Qwen3 embedding and reranker revisions recorded by the repository and load local snapshots at runtime.
- Preserve source identity, chunk hash, model identity/revision, ranking evidence, and conflicts in the result.
- If evidence conflicts or provenance fails, return `NEEDS_EVIDENCE`; do not choose a strategy from the top-ranked passage alone.

### 5. Plan and execute one bounded intervention

1. Generate a baseline and prediction-analysis report.
2. Localize `max_abs` and relate it to boundary conditions, residuals, geometry, time, channel, gradients, or sampling density as appropriate to the PDE.
3. Propose exactly one causal intervention and record its rollback plan.
4. Obtain scoped experiment and smoke approvals.
5. Launch through the governed local-process or AutoDL SSH backend, then reconcile status from durable process identity, heartbeat, exit code, and expected artifacts.
6. Obtain a separate full-run approval before a full run unless an already-recorded authorization covers the exact scope.

### 6. Decide, replay, and promote knowledge

- Compare baseline and candidate only against the same reference identity and compatible coordinates, channels, units, and evaluation basis.
- Evaluate hard constraints and guardrails before primary metric improvements.
- A rejected candidate is a valid governed outcome when evidence, validation consistency, provenance, and replay all pass. Preserve it without claiming improvement.
- Publish to the experiment Wiki only after validation, evidence integrity, reproducibility, replay, and scoped knowledge-promotion approval pass.
- Promote a reusable strategy Skill only after at least two independent validated runs, isolated replay, and explicit Skill-promotion approval. Wiki publication alone is not Skill promotion.

### 7. Verify transfer and release

- Run `scripts/run_release_gates.py --repo-root <system-repo> --python <orchestration-python>`.
- Treat the release allowlist enforced by `scripts/audit_repository.py` as mandatory; do not publish development records or machine-local evidence directories.
- For a transferred full-chain result, run `scripts/verify_completion_bundle.py --result-root <bundle> --expected-commit <git-sha> --expected-source-sha256 <archive-sha>`.
- Compare commit identity, source-archive hash, manifest hash, exact file set, individual file hashes/sizes, final marker, Wiki/RAG gates, and credential scan before accepting the transfer.
- Push only a clean reviewed commit. Confirm repository owner, name, visibility, branch, and diff before changing GitHub state.

## Common requests that trigger this Skill

- "把这个 PINN 项目接入 RAG 多 Agent 决策闭环。"
- "先检查米/毫米、千克/克是否在代码路径中混用。"
- "询问我指标优先级，再定位 max_abs 并提出优化方案。"
- "用 Qwen3 检索 Wiki，但不要让 RAG 直接替我做科学决策。"
- "在另一台机器复现完整 Wiki-RAG-PINN 链路并验证结果包。"
- "审查当前仓库后安全地打包和发布这套 Skill。"

## Stop conditions

Stop and request user direction when the physical model authority, metric priority, reference identity, destructive action, architecture change, repository visibility, or external publication target is not explicit. Stop execution and preserve evidence when a process identity is uncertain, a heartbeat is stale, an artifact is missing, a hash differs, a credential marker is detected, or a scientific comparison is invalid.

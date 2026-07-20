# Unified Operational Closed Loop — Engineering Evidence

Date: 2026-07-20

Status: `ENGINEERING_GATES_PASS_SCIENTIFIC_GATE_AWAITING_USER_METRIC_CONFIRMATION`

## Implemented chain

```text
MCP read-only diagnosis
  -> manifest-driven Project Adapter
  -> LangGraph/CLI audit, approval, execution and collection
  -> aligned-field post-run analysis, metric decision and immutable evidence
```

- `diagnose` runs the existing MCP in an isolated stdio process, verifies the
  tool's read-only/non-destructive annotations and returns source hash plus line
  evidence without creating workflow state.
- `adapt` confines declared paths to the project root, streams SHA-256 over a
  sorted source manifest, replaces placeholder snapshot references and refuses
  to infer physics or overwrite an operator case.
- Existing `audit`, `plan`, `smoke`, `full`, `status` and `replay` gates remain
  authoritative. New `collect` exposes the production backend collection
  contract only for completed runs.
- `evaluate` verifies baseline/candidate/reference NPZ hashes, axes,
  coordinates, reference identity, units and normalization. It localizes
  `max_abs` before calling `MetricDecisionService`, persists comparison,
  decision and evidence-candidate JSON, and never authorizes knowledge
  promotion.

## Verified behavior

- A real `pinn-hybrid-rag` subprocess completed the MCP protocol and returned
  traceable read-only evidence.
- Project path escape and case overwrite are rejected.
- The example lexicographic `max_abs -> RMSE` decision exposes baseline and
  candidate maximum-error coordinates before acceptance and enforces the MAE
  absolute/relative guardrail through the existing deterministic service.
- Misaligned candidate coordinates produce `RESULT_INVALID`, no accepted
  decision and no promotion permission.
- Completed local execution collects its required artifact with source and
  destination manifests; replay launches no second process.
- The current scientific matrix is Poisson, Burgers and two-dimensional heat
  transfer as peers. Lid-driven-cavity NS remains a preserved, inactive and
  non-gating prototype.

## Gate results

- Orchestrator: `150/150 PASS`.
- MCP: `20/20 PASS`.
- OpenSpec strict validation: both active changes `PASS`.
- Credential-marker scan over source and governed documents: `PASS`.
- Architecture isolation: no training/MCP implementation imports, globals,
  implicit working directory or thermal semantics in the generic analyzer.
- Example adapter and post-run JSON contracts: model validation `PASS`.

## Remaining scientific gate

Poisson three-seed qualification cannot start until the user confirms its case
metric contract. The repository intentionally contains no approval record for
that decision. Architecture approval and standing execution authority do not
substitute for metric-priority approval.

After confirmation, the remaining mandatory sequence is: create the scoped
approval record; run frozen seeds `7`, `42` and `2026` in Python 3.11.11 /
PyTorch 2.3.1 / NumPy 2.2.5; aggregate every accepted and rejected outcome;
generate the three-case peer matrix and governed Wiki/Skill candidates without
publication; rerun all release gates and issue the superseding final report.

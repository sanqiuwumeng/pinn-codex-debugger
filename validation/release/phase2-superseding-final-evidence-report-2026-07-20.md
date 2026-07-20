# Phase 2 Superseding Final Evidence Report

- Date: 2026-07-20
- OpenSpec change: `productize-universal-pinn-strategy-system`
- Outcome: **PASS — MANDATORY TASKS COMPLETE**
- Supersedes: `phase2-final-evidence-report-2026-07-17.md`
- Operational-loop implementation: `5f0bfdd`
- Poisson contract closeout: `e5d7f65`
- Peer-evidence assembly fix: `8204348`
- Branch: `exp/hybrid-rag`
- Remote push: not performed

## Final system boundary

The repository now implements the approved three-layer, domain-neutral PINN
strategy system:

```text
read-only MCP diagnosis
  -> manifest-driven project adapter
  -> LangGraph/CLI audit, approval, smoke/full control and collection
  -> aligned post-run field analysis and maximum-error localization
  -> user-confirmed case metric decision
  -> immutable experiment evidence and governed Wiki/Skill candidates
```

The execution layer runs declared experiment commands and collects artifacts.
The orchestration layer carries typed state, approvals and deterministic
decisions. The assurance layer performs physical/unit audit, evaluation-basis
validation, RAG evidence governance, provenance, replay and promotion control.
Functional data crosses these boundaries only through explicit contracts; no
global variables, singleton business state or implicit working directory is a
transport mechanism.

## Actual operator call logic

1. `pinn-strategy diagnose` queries the existing handbook MCP in an isolated
   read-only process and returns traceable source evidence.
2. `pinn-strategy adapt` validates a project manifest, confines all declared
   paths to the project root and emits a deterministic source snapshot plus an
   unresolved operator case. It does not infer physics or metric priority.
3. `audit` validates the user-authoritative physical model and unit
   consistency, including mixed scales such as metre/millimetre or
   kilogram/gram. Non-SI input is permitted when it is explicit and
   consistently converted.
4. `plan` stops at governed `NEEDS_*` states until the reference basis,
   metric ordering, hard constraints, single intervention and approvals are
   explicit.
5. `smoke`, `status`, `full`, `collect` and `replay` use the production backend
   lifecycle. Full execution cannot bypass a validated smoke or scoped
   approval.
6. `evaluate` verifies artifact hashes, coordinates, channels, units,
   normalization and reference identity, then localizes `max_abs` before
   applying the user-confirmed metric contract.
7. Accepted and rejected outcomes remain evidence. Wiki and Skill records are
   only candidates; neither is automatically published.

## Locked runtime boundaries

| Boundary | Runtime | Verified role |
|---|---|---|
| Orchestration | `pinn_strategy_orchestrator`, Python 3.11 | LangGraph, typed contracts, lifecycle and assurance; no training framework import |
| PINN training | `pinn_full_repro_20260716`, Python 3.11.11, PyTorch 2.3.1, NumPy 2.2.5 | Poisson scientific execution on CPU |
| Retrieval model process | isolated model runtime | Frozen Qwen3 embedding/reranking providers through explicit transports |
| MCP | dependency-light isolated stdio process | read-only handbook diagnosis only |

Both local Python environments passed `pip check`. The training versions were
re-probed during this closeout rather than inferred from an old manifest.

## Peer scientific evidence matrix

The active cases have no primary/secondary ranking.

| Peer case | Capability under test | Reference | Case-local metric policy | Outcome |
|---|---|---|---|---|
| Poisson 2D | steady linear elliptic operator and hard boundary constraint | manufactured analytic solution | `relative_l2 -> PDE residual RMS`; boundary max hard constraint | seeds 7, 42, 2026 accepted |
| Viscous Burgers | nonlinear transient transport and high-gradient behavior | independently converged numerical solution | `relative_l2 -> max_abs`; residual and high-gradient guardrails | seed 2026 accepted; 7 and 42 rejected |
| Heat transfer 2D | physical units, consistency and complex thermal boundaries | user-authoritative physical model with test reference evidence | `max_abs -> RMSE`; MAE guardrail | seeds 7 and 42 accepted; 2026 rejected |

The lid-driven-cavity `Re=100` CFD reference, multi-output `u,v,p` worker and
isolated domain provider remain preserved as a
`DEFERRED_NON_GATING_PROTOTYPE`. Full NS qualification is intentionally not a
release gate after the user's scope decision.

Poisson mean `relative_l2` improved by 12.75% across the three frozen seeds.
The detailed values, localized maxima, diagnostics, uncertainty and preserved
failed attempts are recorded in `poisson-qualification-2026-07-20.md`.

## RAG and knowledge governance

The peer evidence matrix and one Wiki/Skill candidate pair were regenerated
from Poisson, Burgers and 2D heat-transfer evidence. Its SHA-256 is
`94b3f8f99985b8bc0a19b2027c40fe8404a31c4b4576b5a65c26c11cddce14fe`.
All 21 embedded artifact references were rehashed and size-checked.

The reusable conclusion is procedural: audit the case, localize error, change
one controlled factor, then let the case-specific contract accept or reject
the intervention. The evidence explicitly contradicts a universal claim that
localized collocation must improve every seed or PDE family. Wiki promotion is
withheld pending human approval; Skill promotion additionally requires an
independent replay.

## Final release gates

| Gate | Result |
|---|---|
| Orchestrator with `ResourceWarning` promoted to error | PASS, 150/150 |
| MCP read-only suite | PASS, 20/20 |
| Poisson and cross-domain regressions | PASS, 4/4 |
| Preserved NS worker contract tests | PASS, 3/3 |
| Frozen Qwen benchmark evaluator tests | PASS, 7/7 |
| Poisson three-seed aggregate | PASS, 3/3 seeds retained |
| Cross-domain candidate generation | PASS, publication false |
| Compileall | PASS |
| Orchestration and training `pip check` | PASS |
| Installed `pinn-strategy --help` | PASS |
| Strict OpenSpec validation | PASS, 2/2 changes |
| Architecture isolation | PASS within the 150-test suite |
| Poisson semantic isolation | PASS, 3/3 |
| Artifact provenance | PASS, 21 candidate references plus 6 Poisson anchors |
| Credential content and filename scan | PASS |
| Git whitespace check | PASS |

## Debug -> First-Principles Refactoring -> Simplification

### Debug

The final qualification exposed three concrete contract defects: the Poisson
reference output channel lacked an explicit unit declaration, the collector
parent did not exist, and the cross-domain generator read the thermal
aggregate's decision string as an object. Failed attempts were retained.

### First-principles refactoring

The fixes restore each source of truth to its owner: the model unit system owns
the output-channel unit, a dedicated helper owns the new collection
destination contract, and one seed-selection function owns the aggregate
decision schema. Regression tests assert those boundaries directly.

### Simplification

No compatibility branch, alternate launcher or validation-only backend was
added. The same production execution, generic comparison, decision,
validation and knowledge-governance services now support all three active peer
cases while their physics and metrics remain isolated.

## Final claim boundary

The project may claim a governed RAG multi-agent PINN strategy system with a
working end-to-end operational loop, production local and AutoDL lifecycle
contracts, frozen Qwen3 retrieval providers, and completed peer validation for
Poisson, Burgers and 2D heat transfer. It may not claim universal scientific
optimality, automatic correctness for an unseen physical model, qualification
of every unit system/PDE/GPU, completed lid-cavity NS science, or permission to
publish Wiki/Skill candidates without the declared human gates.

Large runtime artifacts and both failed Poisson attempts remain in ignored
local evidence. No data was deleted, no knowledge was published and no remote
push was performed during closeout.

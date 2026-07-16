# Phase 2 Final Evidence Report

- Date: 2026-07-17
- OpenSpec change: `productize-universal-pinn-strategy-system`
- Outcome: **SUPERSEDED_BY_PEER_CASE_EXTENSION_IN_PROGRESS**
- Engineering MVP baseline: commit `94641d5`, annotated tag
  `pinn-strategy-mvp-v0.1.0`
- Final scientific implementation batch: commit `6634a92`
- Branch: `exp/hybrid-rag`
- Remote push: not performed

## Correction and extension

On 2026-07-17 the user corrected the case hierarchy and approved an extension:
Poisson, Burgers, lid-driven-cavity Navier-Stokes and 2D heat transfer are peer
scientific validation methods with no primary or secondary status. This report
remains an immutable account of the gates completed through commit `007aaaa`,
but its earlier hierarchy language is superseded. The extension is complete
only after Poisson receives the same governed multi-seed treatment and the new
lid-driven-cavity case passes its declared scientific gates.

## Release outcome through commit `007aaaa`

The approved Phase 2 scope is complete. The repository now has a governed
three-layer PINN strategy system with typed LangGraph orchestration, physical
and unit audits, user-confirmed metric contracts, durable local and AutoDL
execution backends, production Qwen3 retrieval providers, versioned Qdrant
index lifecycle, operator CLI, provenance-safe experiment validation, and
governed Wiki/Skill candidate generation.

Completion means that the declared engineering and scientific gates passed.
It does not mean that every tested optimization was scientifically accepted.
Negative seed outcomes are retained as first-class evidence and are part of
the release result.

## Locked environments

| Boundary | Interpreter/runtime | Locked packages and role |
|---|---|---|
| Orchestration | `pinn_strategy_orchestrator`, Python 3.11.15 | LangGraph 1.2.9, Pydantic 2.13.4, NumPy 2.4.6, SciPy 1.17.1, Qdrant client 1.18.0 |
| PINN training | `pinn_full_repro_20260716`, Python 3.11.11 | PyTorch 2.3.1, NumPy 2.2.5, SciPy 1.15.3; formal thermal and Burgers evidence ran on CPU |
| Retrieval model process | isolated AutoDL model sandbox | PyTorch/model dependencies remain outside the orchestration and PINN training environments |
| AutoDL backend fixture | remote base Python 3.10.8 | dependency-free governed worker; backend qualification only, not PINN training |

The orchestration package does not import PyTorch, TensorFlow or DeepXDE.
Training and model dependencies cross the orchestration boundary only through
explicit manifests or versioned JSONL transport contracts.

## Frozen retrieval models

| Role | Model | Immutable revision | Qualification |
|---|---|---|---|
| Embedding | `Qwen/Qwen3-Embedding-8B` | `1d8ad4ca9b3dd8059ad90a75d4983776a23d44af` | PASS |
| Reranking | `Qwen/Qwen3-Reranker-4B` | `22e683669bc0f0bd69640a1354a6d0aebcfeede5` | PASS |

The production provider path replayed a frozen 15-document, 17-query packet
through the actual embedding and reranking providers. Dense recall@3 was
1.0000, hybrid recall@3 was 0.9375, rerank recall@1 was 1.0000, and every
cross-language, historical, conflict-coverage, deterministic-ranking and
metadata-preservation gate passed. The detailed result SHA-256 is
`b01ccf479b63d2b73495242fa4de6858f5402f323f91b6b46fd6326386c625dd`.

## Execution backend qualification

### Local backend

The production local backend passed success, non-zero exit, missing artifact,
NaN/OOM observation, stale heartbeat, launch timeout, PID-reuse, duplicate
submission, cancellation and interrupted-copy failure injection. The smoke
and full adapters use that same backend; validation-only `Popen` control and
duplicated exit-state mapping were removed.

All eight formal Burgers processes (two smoke, three uniform full baselines and
three focused full candidates) completed through this production path. Replay
proved zero relaunch, and collection verified source and destination manifests.

### AutoDL SSH backend

The remote qualification on an NVIDIA RTX PRO 6000 Blackwell Server Edition
passed prepare, exactly-once launch, simulated lost launch response,
`RUNNING_UNKNOWN` reconciliation, reconnect, bounded status monitoring,
content-addressed collection and repeat collection without overwrite. The
observed remote launch count was exactly one. Endpoint and credential material
are intentionally absent from tracked files and reports.

## Scientific qualification

### Thermal case

The existing thermal focused-collocation case retained the user-confirmed
lexicographic policy `max_abs -> RMSE`, with MAE allowed to regress by no more
than both 1.0 K and 10%. Seeds 7 and 42 were accepted; seed 2026 was rejected
because its absolute MAE regression was 1.1553 K. The rejection remains in the
aggregate. This is a common-baseline seed-uncertainty study, not a paired
uniform-baseline study for every seed.

### Viscous Burgers case

The viscous Burgers peer case uses the classic nonlinear, time-dependent equation
`u_t + u*u_x - (0.01/pi)*u_xx = 0`. Its test reference was generated by an
independent conservative finite-difference/RK4 solver. Relative differences
decreased from `4.987440e-4` (513 versus 1025 nodes) to `1.147762e-4`
(1025 versus 2049 nodes), and all reference gates passed.

The frozen metric policy was lexicographic `relative_l2 -> max_abs`, with hard
initial/boundary constraints and residual/high-gradient guardrails. Across
paired seeds 7, 42 and 2026, only seed 2026 was accepted. Seed 7 violated the
10% high-gradient RMSE gate; seed 42 regressed the first primary. The result
validates governed diagnosis, execution, rejection and provenance across a
second PDE family. It does not validate localized collocation as a universal
optimization rule.

### Poisson and lid-driven-cavity extension scope

The manufactured-solution two-dimensional Poisson implementation is a peer
scientific case and must now complete the same governed multi-seed lifecycle.
The approved lid-driven-cavity extension adds a `Re=100`, multi-output
incompressible Navier-Stokes peer case with an independently converged CFD
reference and Ghia centerline cross-validation.

## Knowledge governance

Cross-domain evidence supports the reusable workflow pattern: validate the
case, localize the baseline error, change one controlled factor, and let the
case-specific contract accept or reject it. It does not support a universal
focused-sampling strategy.

One Wiki candidate and one Skill candidate were created with complete evidence
references. Neither was published. Wiki promotion still requires explicit
human approval; Skill promotion additionally requires independent replay.

## Final release gates

| Gate | Result |
|---|---|
| Orchestrator suite with `ResourceWarning` promoted to error | PASS, 140 tests |
| MCP suite | PASS, 20 tests |
| Installed `pinn-strategy.exe --help` | PASS |
| Backend, CLI, retrieval and architecture-boundary coverage | PASS within the orchestrator suite |
| Compileall | PASS |
| `pip check` | PASS, no broken requirements |
| Strict OpenSpec validation | PASS, 2/2 changes |
| Credential-pattern scan | PASS |
| Absolute-path / cwd-independence audit | PASS |
| Global/nonlocal state audit | PASS |
| Orchestration training-import isolation | PASS |
| Artifact provenance audit | PASS, 88 unique references plus frozen Qwen result |
| Burgers semantic-isolation audit | PASS, zero violations |
| Git whitespace check | PASS |

## Debug -> First-Principles Refactoring -> Simplification

### Debug

Live qualification exposed and closed concrete defects without weakening the
gates: local and AutoDL process-identity edge cases, remote JSON framing,
credential-safe exception handling, CLI experiment-completeness ordering,
thermal backend provisioning, a Burgers high-gradient test fixture that placed
all selected error at a hard-zero boundary, and a missing dimensionless `u`
quantity declaration. Failed attempts and scientific rejections were preserved.

### First-principles refactoring

Execution truth now comes from durable manifests, process identity, append-only
events, heartbeats and verified artifacts rather than live object state. Model
truth comes from the user-authoritative physical contract, unit consistency,
reference evidence and case-local metrics. The Burgers qualification therefore
reuses the production backend, generic prediction analyzer, decision service,
validation service and knowledge-governance service instead of implementing an
alternate scientific control path.

### Simplification

One production backend replaced adapter-specific launch logic. One explicit
transport boundary isolates Qwen runtimes. Each peer case uses the same
governance lifecycle but keeps its own physics, units, references and metrics.
Mixed scientific outcomes generate bounded candidates, not automatic Wiki or
Skill publication.

## Claim boundary

The evidence through commit `007aaaa` may claim that the declared architecture
and governance lifecycle operated across the completed thermal and Burgers
qualifications and the implemented Poisson pathway, with durable local/AutoDL
execution and frozen Qwen3 retrieval. It must
not claim that every PINN, PDE family, physical unit system, optimization
strategy, GPU environment or reference type is already scientifically
qualified. New PDE families still require their own authority, unit audit,
reference, user-confirmed metric ordering, localized diagnosis and multi-seed
evidence.

Large runtime artifacts remain in the ignored evidence area. Tracked reports
retain immutable SHA-256 anchors; no remote push or knowledge publication was
performed as part of this closeout.

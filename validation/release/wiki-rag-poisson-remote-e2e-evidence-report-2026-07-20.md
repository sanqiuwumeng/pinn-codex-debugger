# Wiki + Qwen RAG + Poisson remote end-to-end evidence report

## Outcome

The governed remote chain completed successfully against source commit
`432f7601a25e487f9656c63234776349338e1362`. It formally published Wiki
`peer-pinn-localized-collocation` version 1, verified an identical publication
replay, rebuilt the vector index with the pinned Qwen providers, retrieved the
published Wiki as the top reranked result, exposed a known unit conflict, and
completed an independent Poisson PINN audit, smoke/full comparison, decision,
artifact collection and zero-relaunch replay.

This is a PASS for system and governance completeness. The seed-local focused
collocation candidate was correctly rejected, so this report makes no claim of
scientific improvement or universal PINN effectiveness. No Skill was published.

## Exact source and isolated runtimes

- Git source commit: `432f7601a25e487f9656c63234776349338e1362`
- Git archive SHA-256: `ca39efd914ac877980608c5e225f02113717c478f61fe5df07a4e251cc3773e5`
- Remote version root: `/root/autodl-tmp/pinn-rag-wiki-e2e-20260720-432f760`
- Orchestrator: Python 3.11.11, Pydantic 2.13.4, Qdrant client 1.18.0
- Retrieval GPU runtime: PyTorch 2.12.1+cu130 on NVIDIA RTX PRO 6000 Blackwell;
  a real CUDA matrix multiplication completed before model loading.
- PINN runtime: Python 3.11.11, PyTorch 2.3.1+cu121, NumPy 2.2.5.

The current Blackwell GPU cannot execute kernels from PyTorch 2.3.1 because
that build does not contain `sm_120` support. The Poisson worker therefore ran
on CPU in the user-designated PyTorch 2.3.1 environment, while Qwen inference
ran on GPU in its physically separate compatible environment. The two layers
communicated only through serialized contracts and artifacts.

## Formal Wiki publication

The production `wiki publish` command returned `WIKI_PUBLISHED`; an identical
second call returned `WIKI_VERIFIED`. The immutable version directory contains:

| File | SHA-256 |
|---|---|
| `publication.json` | `4ec41d89da7bf63f2034b45263d894bc06c63a926e4afc53f982cf746cf6b308` |
| `entry.md` | `fb20b9fa3d8e87801691ad390974206e81f386e46f5bc90b519020b8bdbd63dc` |
| `entry.index.json` | `c0d5ef18e325843c3550d561ebf532938c444ab08aa778a887ab71c05cf6d325` |
| `manifest.json` | `6f1498815ee5aec4423c89a57bbec26fdb3e750e88d51209be90ebc529c30d56` |

The related Skill candidate remains unpromoted. The Wiki version is present in
the transferred authoritative knowledge directory and can rebuild the derived
Qdrant state without treating Qdrant as the knowledge source of truth.

## Qwen retrieval evidence

- Embedding: `Qwen/Qwen3-Embedding-8B`, revision
  `1d8ad4ca9b3dd8059ad90a75d4983776a23d44af`, vector size 4096.
- Reranker: `Qwen/Qwen3-Reranker-4B`, revision
  `22e683669bc0f0bd69640a1354a6d0aebcfeede5`.
- The published Wiki chunk `peer-pinn-localized-collocation-v0001` ranked first
  with reranker score 3.375.
- A separate query exposed `radiation_temperature_unit` values `K` and `degC`
  from distinct evidence items; `decision_safe` was false.
- Retrieved knowledge remained advisory. Measured fields and the approved
  Poisson metric contract retained final decision authority.

## Independent Poisson result

Seed `314159` ran uniform and focused smoke/full stages. The intervention kept
the equation, analytic reference, boundary ansatz, geometry, network,
initialization, optimizer, schedule, epoch budget, point count and evaluation
grid unchanged; it changed only 12.5% of collocation sampling around the
diagnosed baseline maximum.

| Metric | Uniform baseline | Focused candidate | Delta |
|---|---:|---:|---:|
| relative L2 | 0.0001850753 | 0.0002904950 | +0.0001054198 |
| max abs | 0.0003156066 | 0.0005048513 | +0.0001892447 |
| RMSE | 0.0000911140 | 0.0001430129 | +0.0000518990 |
| MAE | 0.0000664116 | 0.0001029401 | +0.0000365285 |

The baseline maximum occurred at `(x=0.515625, y=0.4375)` with signed error
`-0.0003156066`. The candidate maximum migrated to
`(x=0.71875, y=0.359375)` with signed error `+0.0005048513`.

The approved case decision was `REJECT` because primary `relative_l2`
regressed. The rollback retained the uniform baseline and preserved candidate
evidence. Candidate validation was therefore consistently `RESULT_INVALID`;
this is not a failed workflow. Baseline validity, aligned comparison, smoke,
terminal decision, validation consistency, evidence integrity, provenance,
worker immutability, semantic isolation and replay all passed. The completion
record explicitly sets `governance_outcome=REJECTION_RETAINED` and
`scientific_improvement_claimed=false`.

## Completion and transfer integrity

- Remote status: `0`; log contains `EXIT_STATUS=0`.
- Full-chain duration: 117.707155 seconds.
- Completion manifest SHA-256:
  `6fa63783a986af6d681184bc2344e271be8b022f896961564179d476f88d8808`.
- Poisson report SHA-256:
  `ccaf69a52b3bda0a5aa534840e0c853383305dff50c9d88e3431698bd01785da`.
- Completion manifest entries: 269; transferred files including the manifest
  and final marker: 271; exact file bytes: 4,014,425.
- Remote and local credential scans: PASS.
- Every manifest entry, file size, SHA-256, Wiki sub-manifest and final marker
  was revalidated after the one-time transfer.

The local evidence root is
`validation/phase2/results/remote-e2e-full-chain-20260720-432f760/`.

## Preserved failed evidence

No failed evidence was deleted or overwritten. Earlier version directories
remain on the remote instance and record four defects closed during the run:

1. `bdaacc6`: a Windows-specific test URI conversion failed on Linux.
2. `3a96e28`: the outer assertion used a non-production active-index field name.
3. `e3f562a`: resolving a virtualenv launcher symlink crossed the orchestrator/
   PINN environment boundary before process identity could be recorded.
4. `1752643`: the outer completion gate assumed every complete workflow must
   accept the candidate and read semantic isolation from the wrong report level.

## Debug -> First-Principles Refactoring -> Simplification

### Debug

Each failure was diagnosed from preserved status, structured step output and
production artifacts. No scientific threshold, reranking requirement,
conflict gate, process-identity check or provenance check was weakened.

### First-principles refactoring

File URIs now use platform-aware parsing; active-index validation follows the
declared production schema; virtualenv identity is the invoked absolute path,
not the resolved binary target; and workflow completeness is separated from a
candidate's scientific acceptance through an explicit decision-to-validation
mapping.

### Simplification

The final chain has one immutable Wiki publication path, one derived RAG index,
one advisory retrieval boundary, one deterministic Poisson decision contract
and one completion manifest. Rejected science remains a valid governed outcome
without adding a compatibility launcher, alternate backend or acceptance
bypass.

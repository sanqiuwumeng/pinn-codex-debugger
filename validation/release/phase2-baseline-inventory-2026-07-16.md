# Phase 2 Selective Baseline Inventory

- Date: 2026-07-16
- Branch: `exp/hybrid-rag`
- Pre-baseline HEAD: `c3ce4c3`
- Change: `productize-universal-pinn-strategy-system`
- Policy: preserve all local evidence; commit source, tests, OpenSpec, final reports and small provenance records only

## Uncommitted workspace classification

| Root | Classification | Pre-ignore files | Pre-ignore bytes | Git policy |
| --- | --- | ---: | ---: | --- |
| `mcp-server/tests` | restored regression source plus dated backups/cache | 21 | 65,364 | track Python tests; exclude cache/backups |
| `openspec` | Phase 1/2 specifications, approvals and dated backups | 31 before Phase 2 additions | 196,601 before Phase 2 additions | track live specs/approvals; exclude backups |
| `orchestrator` | runtime source, tests, package metadata, cache and dated backups | 188 | 1,456,494 | track source/tests/metadata; exclude cache/backups |
| `validation` | adapters, reports, manifests, generated outputs and backups | 430 before this inventory | 103,564,384 before this inventory | track adapters/reports/small manifests; exclude generated/binary/runtime evidence and backups |
| `README.md` | product documentation | 1 | 5,648 | track after review; existing modification must remain untouched until separately backed up |

## Preserved artifact-store roots

These paths remain on disk and are intentionally excluded from Git. No cleanup or deletion was performed.

| Path | Files | Bytes | Authority |
| --- | ---: | ---: | --- |
| `validation/smoke/results` | 148 | 6,386,771 | governed smoke run and replay evidence |
| `validation/full/results` | 98 | 60,036,286 | authoritative exact-environment full run and replay evidence |
| `validation/full/preflight` | 48 | 2,081,830 | exact-environment preflight workspace/output |
| `validation/benchmarks/results` | 36 | 228,768 | verified AutoDL Qwen3 benchmark transfer evidence |
| `validation/dependencies` | 17 | 33,874,230 | dependency manifests plus large install/dry-run logs; small human-readable manifests remain trackable |
| `validation/backups` | 36 before this baseline backup | 355,263 before this baseline backup | required dated safety backups |

## Authoritative excluded evidence anchors

| Evidence manifest | Bytes | SHA-256 |
| --- | ---: | --- |
| `validation/full/results/pinn2d-focused-full-repro-20260716/runtime/artifacts/full-evidence-manifest.json` | 6,652 | `ff99f6c7a00775ea2b03a496f5c79eda3523ae64380bcb122a2c36a316156206` |
| `validation/smoke/results/universal-pinn-smoke-20260716/runtime/artifacts/evidence-manifest.json` | 8,986 | `9d317b8ed785090251aaae9ecfa7c5c36967af10335850de11a3d5635357f5a2` |
| `validation/benchmarks/results/autodl-a6000/qwen3_remote_session_20260716T051709Z_verified/run_logs/qwen3_session_evidence_sha256_20260716T0601Z.txt` | 4,206 | `08a0c9d78abc2233cd5faef5775091c6132071d669105b293cb74ff8fed14301` |

Tracked summary reports retain the scientific meaning and point to these local artifact manifests:

- `validation/full/full-run-qualification-report-2026-07-16.md`
- `validation/smoke/mvp-release-gate-report-2026-07-16.md`
- `validation/benchmarks/qwen3-autodl-formal-benchmark-2026-07-16.md`

## Ignore policy

The dated `.gitignore` backup is stored at `validation/backups/2026-07-16-phase2-release-baseline/.gitignore_backup_2026-07-16`. New ignore rules cover safety backups, generated results/preflight workspaces, runtime databases and process files, numerical/model binaries, rendered figures, archives, full logs and large pip dry-run JSON. They do not ignore source, tests, OpenSpec, final Markdown reports, small environment manifests or governed case adapters.

## Credential-risk scan

A filename-only high-signal scan covered private-key headers, direct SSH command patterns, AutoDL connection-domain patterns and password assignments outside known third-party dependency dumps. It returned no repository match. A final full staged-content scan remains mandatory immediately before the baseline commit.

## Baseline gate still pending

This inventory and ignore policy do not create a commit. The selective staged set must still pass orchestrator tests, MCP tests, strict OpenSpec validation, compile checks, architecture isolation, `git diff --check` and a staged credential scan before a baseline commit identity is recorded.

# Phase 2 Baseline Record

- Baseline commit: `94641d5`
- Local annotated tag: `pinn-strategy-mvp-v0.1.0`
- Branch: `exp/hybrid-rag`
- Remote push: not performed
- Large local evidence: preserved and ignored according to `phase2-baseline-inventory-2026-07-16.md`

## Gate results

| Gate | Result |
| --- | --- |
| Orchestrator regression | PASS, 94 tests |
| MCP regression | PASS, 20 tests |
| Orchestrator `pip check` | PASS |
| Compileall | PASS |
| Strict OpenSpec validation | PASS, 2 changes |
| Architecture boundary suite | PASS as part of orchestrator regression |
| `git diff --cached --check` | PASS |
| High-signal staged credential content scan | PASS |
| Credential-risk staged filename scan | PASS |

## Closed-loop review

### Debug

The initial staged diff exposed CRLF JSON records and redundant EOF blank lines. The affected files and `.gitattributes` were backed up before correction.

### First-principles refactoring

Repository text policy now declares deterministic line endings by file type. Large and generated experiment evidence remains outside Git, while tracked reports retain immutable SHA-256 anchors to authoritative local manifests.

### Simplification

The baseline contains 131 tracked changes instead of approximately 104.7 MB of runtime evidence. No artifact, backup, model, array, database or log was deleted, and no remote push was attempted.

## Release boundary

This tag identifies the verified engineering MVP and the approved Phase 2 specification. It is not a claim that production backends, Qwen3 providers, CLI or cross-domain scientific qualification are already complete; those remain open tasks in `productize-universal-pinn-strategy-system`.

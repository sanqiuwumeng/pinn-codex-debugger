## 1. Governance

- [x] 1.1 Record the user's explicit `Yes` for formal Wiki publication and the AutoDL end-to-end run.
- [x] 1.2 Reuse the approved isolated local and remote environments without adding a package.
- [x] 1.3 Back up every existing implementation or documentation file before modification.

## 2. Formal Wiki Publication

- [x] 2.1 Add `WikiPublicationSpec`, `PublishedWikiEntry` and publication receipt contracts with strict approval and scope validation.
- [x] 2.2 Add `KnowledgeGovernanceService.publish_wiki` without weakening candidate or Skill gates.
- [x] 2.3 Implement an append-only atomic Wiki store that emits JSON, Markdown, RAG index and SHA-256 manifest files.
- [x] 2.4 Add an application service and `pinn-strategy wiki publish` with explicit absolute paths and stable JSON output.
- [x] 2.5 Prove wrong approval kind/scope, invalid candidate, earlier publication time, path escape and conflicting overwrite all fail without publication.

## 3. Local Qualification and Sync

- [x] 3.1 Run focused and full orchestrator/MCP/OpenSpec/credential/architecture gates in the approved local sandbox.
- [x] 3.2 Commit the implementation and sync that exact Git archive into a new versioned AutoDL directory with hash verification.
- [x] 3.3 Verify remote Qwen and PINN environments plus real GPU kernels before the formal chain.

## 4. Remote End-to-End Qualification

- [x] 4.1 Publish the approved cross-domain Wiki version through the production CLI; do not publish the Skill candidate.
- [x] 4.2 Build and activate a Qdrant index from the authoritative Wiki source using the pinned Qwen3 embedding provider.
- [x] 4.3 Retrieve and rerank the published Wiki with the pinned Qwen3 reranker and verify provenance, revision and conflict visibility.
- [x] 4.4 Run an independent Poisson PINN audit, smoke/full execution, collection, maximum-error localization, approved metric decision and immutable evidence.
- [x] 4.5 Replay the completed execution without relaunch and prove the PINN decision cites retrieved knowledge only as advisory evidence.
- [x] 4.6 Preserve failed/rejected evidence and produce a credential-free remote completion manifest.

## 5. Closeout

- [x] 5.1 Verify remote exit marker, logs, artifact count, sizes and hashes before one-time result transfer.
- [x] 5.2 Back up any existing local destination, transfer results once and revalidate locally.
- [x] 5.3 Run final release gates, issue a tracked evidence report and close this change only when no mandatory task remains.

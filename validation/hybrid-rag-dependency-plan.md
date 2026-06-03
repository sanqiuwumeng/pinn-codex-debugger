# Hybrid-RAG Dependency Plan

## Decision

- Date: `2026-06-03`
- User approval for architecture: explicit `Yes`
- Sandbox plan: reuse existing `pytorch2.3.1`; no new conda sandbox
- External package installation: none
- Embedding model download: none

## Backend

- Backend id: `stdlib-concept-charngram-v1`
- Retrieval method: deterministic rules anchors + concept lexicon + token overlap + character 3-gram similarity
- Index format: in-memory section documents generated from the repository handbook at runtime
- Persisted evidence format: JSONL replay artifacts under `validation/hybrid-rag/`

## Reproducibility Inputs

- Handbook SHA256: `C7D3DD557F7942D6E10FE4331162297C07AF68AFFEC165066BC21CF8CE48EF16`
- Section parser: `rules_mcp.handbook.HandbookIndex`
- Concept source: `hybrid_rag.lexicon.build_concept_lexicon()`
- Benchmark source: `validation/blind-tests/2026-06-02_nine-family-baseline/prompts.jsonl`

## Resource Cost

- Runtime dependencies: Python standard library only
- Network use: none
- GPU use: none
- Index storage: rebuilt in memory from handbook sections
- Expected runtime: sub-second scale for unit tests; replay script completes within a few seconds in `pytorch2.3.1`

## Boundary Decision

`hybrid-rag` reuses the deterministic extractor through an explicit boundary:

- `rules_mcp.handbook.HandbookIndex` provides source sections and SHA provenance.
- `rules_mcp.service.RulesRetrievalService` provides the deterministic family record.
- `hybrid_rag.HybridRetrievalService` receives both as constructor arguments and returns explicit ranked-section responses.

No global mutable state, singleton service, background process, package install, or hidden dependency is used.

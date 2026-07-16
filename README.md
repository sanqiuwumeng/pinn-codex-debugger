# PINN Hybrid RAG

PINN Hybrid RAG combines a local, deterministic MCP evidence service with a
governed orchestration package for strategy optimization across general
Physics-Informed Neural Network (PINN) models.

The MCP product remains read-only. The separate `orchestrator` package adds
versioned contracts, LangGraph gates, physical-model assurance, metric-policy
decisions, provider-scoped diagnostics, experiment governance and persistent
evidence boundaries without moving those side effects into the MCP server.

## Architecture Scope

The strategy system is PINN-general rather than heat-transfer-specific:

- the user's PDE, BC, IC, geometry and parameters define the physical authority;
- analytic, experimental, numerical and teacher data are optional reference
  evidence, not universal truth sources;
- model units may be SI or non-SI when their conversion chain is explicit and
  internally consistent;
- generic field metrics and localization stay in the core;
- heat transfer, fluid, elasticity, wave and inverse-problem metrics are loaded
  only through explicitly selected domain providers;
- ROI, time windows, thresholds and provider selection belong to each case
  contract.

## What It Does

- Routes observable PINN symptoms to a deterministic diagnosis family.
- Retrieves traceable handbook sections with source hash and line ranges.
- Adds hybrid recall through rules anchors, concept lexicons, token overlap, and
  character 3-gram matching.
- Returns structured MCP responses that can be consumed by Codex or another MCP
  client.

The service is read-only. It does not modify PINN projects, start training jobs,
install packages, call network APIs, or use background state.

## Product Scope

This package is useful as a debugging assistant for:

- boundary-condition or initial-condition failure
- late-time divergence
- local residual hot spots
- high-frequency smoothing
- inverse-parameter drift
- conservation drift
- high-order PDE instability
- repeated parametric solves
- underspecified PINN failures

It should be treated as an evidence and routing layer. Final code edits and
training decisions should still go through normal engineering review.

## Repository Layout

```text
.
|-- PINN报错诊断与模块选择手册.md
|-- README.md
|-- mcp-server/
|   |-- README.md
|   |-- mcp-config.example.json
|   |-- pyproject.toml
|   |-- pinn_hybrid_rag/
|   |   `-- resources/
|   |-- hybrid_rag/
|   `-- rules_mcp/
|-- orchestrator/
|   |-- pyproject.toml
|   |-- src/pinn_strategy_system/
|   `-- tests/
|-- openspec/
`-- validation/
```

## Requirements

- Python 3.11 or compatible modern Python
- The MCP package has no third-party runtime dependency
- The orchestration package uses the separately approved
  `pinn_strategy_orchestrator` conda environment
- UTF-8 capable terminal or MCP client

Use any Python 3.11+ interpreter on the target machine. If your MCP client uses
`mcp-server/mcp-config.example.json`, replace `PATH_TO_REPOSITORY` with the
local checkout path.

## Install

For source-tree use without installing:

```powershell
$env:PYTHONUTF8='1'
Set-Location 'PATH_TO_REPOSITORY\mcp-server'
python -m pinn_hybrid_rag
```

For editable installation:

```powershell
Set-Location 'PATH_TO_REPOSITORY\mcp-server'
python -m pip install -e .
```

After editable installation, start the MCP server with:

```powershell
pinn-hybrid-rag
```

Each MCP request and response is one UTF-8 JSON-RPC object per line. A client
must send `initialize`, then `notifications/initialized`, before calling tools.

## Smoke Test

```powershell
Set-Location 'PATH_TO_REPOSITORY\mcp-server'
python -B smoke_test.py
```

## MCP Tools

### `hybrid_search_pinn_handbook`

Main product tool. It ranks handbook sections using deterministic hybrid
retrieval.

Input:

```json
{
  "query": "t=5 early phase interface is wrong and local residual is high",
  "evidence": ["boundary values are already correct"],
  "anchors": [],
  "max_sections": 5
}
```

Output includes:

- inferred diagnosis family
- rules family
- matched concepts
- backend description
- source handbook SHA256
- ranked sections with score breakdowns, line ranges, matched terms, matched
  concepts, matched anchors, and excerpts

### `diagnose_pinn_symptom`

Routes one symptom into a deterministic symptom family and returns required
basic checks, evidence gaps, candidate anchors, and handbook matches.

### `search_pinn_handbook`

Performs direct handbook section search using explicit query terms or anchors.

## Example MCP Config

See:

```text
mcp-server/mcp-config.example.json
```

Update the Python path and `cwd` if you place the repository somewhere else.

The recommended module entrypoint is:

```text
python -m pinn_hybrid_rag
```

The legacy module entrypoint `python -m rules_mcp` remains as a thin forwarder,
but new MCP clients should use `pinn_hybrid_rag`.

## Design Principles

- explicit request and response models
- no global mutable state
- no network dependency
- no embedding service dependency
- deterministic output for the same handbook and query
- source-grounded evidence with hashes and line ranges

## Included Handbook

The source handbook is:

```text
PINN报错诊断与模块选择手册.md
```

For source-tree and editable runs, the service reads the repository-root
handbook. For package installs, the same handbook is also included as package
data under `pinn_hybrid_rag/resources/`.

To force a specific handbook path, set:

```powershell
$env:PINN_HYBRID_RAG_HANDBOOK='C:\path\to\PINN报错诊断与模块选择手册.md'
```

The service builds its section index from the selected handbook at startup.

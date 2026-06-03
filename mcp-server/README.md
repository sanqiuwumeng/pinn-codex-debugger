# MCP Server

This directory contains the runtime source for the PINN Hybrid RAG MCP service.

## Packages

- `pinn_hybrid_rag`: product entrypoint and composition root.
- `rules_mcp`: stdio MCP server, symptom routing, direct handbook search, and
  JSON-RPC handling. This is an internal support package.
- `hybrid_rag`: deterministic hybrid retrieval over handbook sections.

The composition root is `pinn_hybrid_rag.__main__`. It constructs the handbook
index, rules service, hybrid section index, and hybrid retrieval service
explicitly, then injects them into the MCP server.

The package includes a copy of the handbook under
`pinn_hybrid_rag/resources/` for installed-package runs. Source-tree and editable
runs prefer the repository-root handbook. Set `PINN_HYBRID_RAG_HANDBOOK` to
force a specific handbook file.

## Install

```powershell
Set-Location 'PATH_TO_REPOSITORY\mcp-server'
python -m pip install -e .
```

## Run

```powershell
$env:PYTHONUTF8='1'
Set-Location 'PATH_TO_REPOSITORY\mcp-server'
python -m pinn_hybrid_rag
```

After editable installation, you can also run:

```powershell
pinn-hybrid-rag
```

## Smoke Test

```powershell
python -B smoke_test.py
```

## Tools

- `hybrid_search_pinn_handbook`: main hybrid-rag retrieval tool.
- `diagnose_pinn_symptom`: deterministic symptom-family routing.
- `search_pinn_handbook`: direct handbook section search.

## Notes

- Python standard library only.
- No package installation required.
- No network access required.
- The server reads the selected handbook at startup and reports its SHA256.

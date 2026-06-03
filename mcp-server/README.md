# MCP Server

This directory contains the runtime source for the PINN Hybrid RAG MCP service.

## Packages

- `rules_mcp`: stdio MCP server, symptom routing, direct handbook search, and
  JSON-RPC handling.
- `hybrid_rag`: deterministic hybrid retrieval over handbook sections.

The composition root is `rules_mcp.__main__`. It constructs the handbook index,
rules service, hybrid section index, and hybrid retrieval service explicitly,
then injects them into the MCP server.

## Run

```powershell
$env:PYTHONUTF8='1'
Set-Location 'E:\vibe coding\pinn-codex-debugger.worktrees\hybrid-rag\mcp-server'
& 'C:\Users\Mli\.conda\envs\pytorch2.3.1\python.exe' -m rules_mcp
```

## Tools

- `hybrid_search_pinn_handbook`: main hybrid-rag retrieval tool.
- `diagnose_pinn_symptom`: deterministic symptom-family routing.
- `search_pinn_handbook`: direct handbook section search.

## Notes

- Python standard library only.
- No package installation required.
- No network access required.
- The server reads the repository-root handbook at startup.

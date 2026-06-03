# PINN Rules MCP Server

Local, read-only MCP server for deterministic PINN symptom routing and handbook evidence extraction.

## Runtime

- Python standard library only
- stdio transport
- MCP protocol revision: `2025-11-25`
- Source handbook: repository-root `PINN报错诊断与模块选择手册.md`

## Run

```powershell
$env:PYTHONUTF8='1'
Set-Location 'E:\vibe coding\pinn-codex-debugger.worktrees\rules-mcp\mcp-server'
& 'C:\Users\Mli\.conda\envs\pytorch2.3.1\python.exe' -m rules_mcp
```

Each request and response is one UTF-8 JSON-RPC object per line.
The client must send `initialize`, then `notifications/initialized`, before invoking tools.

## Tools

- `diagnose_pinn_symptom`: classify one observable symptom and return evidence gaps, required checks, candidate anchors, and traceable handbook matches.
- `search_pinn_handbook`: retrieve exact-match handbook sections with source hash and line ranges.

The server does not use embeddings, network access, background services, global mutable state, or external packages.

# Rules-MCP Dependency Plan

## Approval

- Architecture approval: user replied `Yes` on `2026-06-02`.
- Sandbox decision: do not create a conda sandbox.
- Existing environment: `C:\Users\Mli\.conda\envs\pytorch2.3.1`

## Dependencies

- Runtime: Python `3.11.11`
- External packages: none
- MCP SDK: not installed and not required
- Test framework: standard-library `unittest`
- Transport: local stdio with newline-delimited UTF-8 JSON-RPC messages

## Scope

- Implement only inside `exp/rules-mcp`.
- Keep the source handbook byte-identical.
- Use explicit request and response objects.
- Do not use embeddings, vector search, background services, global mutable state, or implicit cross-module dependencies.

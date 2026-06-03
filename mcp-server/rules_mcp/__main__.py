"""Legacy module entrypoint for the PINN Hybrid RAG MCP server."""

from __future__ import annotations

from pinn_hybrid_rag.__main__ import create_server, main

__all__ = ["create_server", "main"]


if __name__ == "__main__":
    main()

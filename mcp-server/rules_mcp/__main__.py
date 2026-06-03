"""Composition root for the local PINN rules MCP server."""

from __future__ import annotations

from pathlib import Path

from .catalog import build_rules
from .handbook import HandbookIndex
from .server import StdioMcpServer, run_stdio_server
from .service import RulesRetrievalService


def create_server() -> StdioMcpServer:
    repo_root = Path(__file__).resolve().parents[2]
    handbook_path = repo_root / "PINN报错诊断与模块选择手册.md"
    service = RulesRetrievalService(
        handbook_index=HandbookIndex.from_path(handbook_path),
        rules=build_rules(),
    )
    return StdioMcpServer(service)


if __name__ == "__main__":
    run_stdio_server(create_server())

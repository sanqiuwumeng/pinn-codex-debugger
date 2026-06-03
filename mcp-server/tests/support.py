"""Shared explicit test fixtures."""

from __future__ import annotations

from pathlib import Path

from rules_mcp import HandbookIndex, RulesRetrievalService, build_rules
from rules_mcp.server import StdioMcpServer


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def create_service() -> RulesRetrievalService:
    return RulesRetrievalService(
        handbook_index=HandbookIndex.from_path(
            repo_root() / "PINN报错诊断与模块选择手册.md"
        ),
        rules=build_rules(),
    )


def create_server() -> StdioMcpServer:
    return StdioMcpServer(create_service())

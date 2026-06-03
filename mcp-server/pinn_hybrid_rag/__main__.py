"""Composition root for the PINN Hybrid RAG MCP product."""

from __future__ import annotations

import os
from pathlib import Path

from hybrid_rag.index import HybridSectionIndex
from hybrid_rag.lexicon import build_concept_lexicon
from hybrid_rag.service import HybridRetrievalService
from rules_mcp.catalog import build_rules
from rules_mcp.handbook import HandbookIndex
from rules_mcp.server import StdioMcpServer, run_stdio_server
from rules_mcp.service import RulesRetrievalService

HANDBOOK_FILENAME = "PINN报错诊断与模块选择手册.md"
HANDBOOK_ENV_VAR = "PINN_HYBRID_RAG_HANDBOOK"


def default_repo_root() -> Path:
    """Return the repository root for source-tree and editable installs."""
    return Path(__file__).resolve().parents[2]


def default_handbook_path(repo_root: Path | None = None) -> Path:
    """Locate the handbook for source-tree, editable, and wheel installs."""
    env_path = os.environ.get(HANDBOOK_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser().resolve()

    resolved_root = (repo_root or default_repo_root()).resolve()
    source_tree_path = resolved_root / HANDBOOK_FILENAME
    if source_tree_path.exists():
        return source_tree_path

    return Path(__file__).resolve().parent / "resources" / HANDBOOK_FILENAME


def create_server(repo_root: Path | None = None) -> StdioMcpServer:
    """Create the MCP server with explicit product dependencies."""
    handbook_path = default_handbook_path(repo_root)
    handbook_index = HandbookIndex.from_path(handbook_path)
    rules = build_rules()
    concepts = build_concept_lexicon()
    rules_service = RulesRetrievalService(
        handbook_index=handbook_index,
        rules=rules,
    )
    hybrid_service = HybridRetrievalService(
        section_index=HybridSectionIndex.from_handbook(handbook_index, concepts),
        rules_service=rules_service,
        rules=rules,
        concepts=concepts,
    )
    return StdioMcpServer(rules_service, hybrid_service)


def main() -> None:
    """Run the stdio MCP server."""
    run_stdio_server(create_server())


if __name__ == "__main__":
    main()

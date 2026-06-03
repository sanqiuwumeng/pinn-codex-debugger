"""Composition root for the local PINN rules MCP server."""

from __future__ import annotations

from pathlib import Path

from hybrid_rag.index import HybridSectionIndex
from hybrid_rag.lexicon import build_concept_lexicon
from hybrid_rag.service import HybridRetrievalService

from .catalog import build_rules
from .handbook import HandbookIndex
from .server import StdioMcpServer, run_stdio_server
from .service import RulesRetrievalService


def create_server() -> StdioMcpServer:
    repo_root = Path(__file__).resolve().parents[2]
    handbook_path = repo_root / "PINN报错诊断与模块选择手册.md"
    handbook_index = HandbookIndex.from_path(handbook_path)
    rules = build_rules()
    concepts = build_concept_lexicon()
    service = RulesRetrievalService(
        handbook_index=handbook_index,
        rules=rules,
    )
    hybrid_service = HybridRetrievalService(
        section_index=HybridSectionIndex.from_handbook(handbook_index, concepts),
        rules_service=service,
        rules=rules,
        concepts=concepts,
    )
    return StdioMcpServer(service, hybrid_service)


if __name__ == "__main__":
    run_stdio_server(create_server())

"""Explicit service factories shared by regression tests."""

from __future__ import annotations

from pathlib import Path

from hybrid_rag import (
    HybridRetrievalService,
    HybridSectionIndex,
    build_concept_lexicon,
)
from pinn_hybrid_rag.__main__ import create_server
from rules_mcp import HandbookIndex, RulesRetrievalService, build_rules
from rules_mcp.server import StdioMcpServer


def repo_root() -> Path:
    """Return the repository root containing the source handbook."""
    return Path(__file__).resolve().parents[2]


def expected_handbook_sha256() -> str:
    """Return the frozen handbook provenance expected by product tests."""
    return "C7D3DD557F7942D6E10FE4331162297C07AF68AFFEC165066BC21CF8CE48EF16"


def create_rules_service() -> RulesRetrievalService:
    """Build a rules service from explicit immutable dependencies."""
    handbook_index = HandbookIndex.from_path(
        repo_root() / "PINN报错诊断与模块选择手册.md"
    )
    return RulesRetrievalService(handbook_index, build_rules())


def create_hybrid_service() -> HybridRetrievalService:
    """Build a hybrid service from the production composition dependencies."""
    handbook_index = HandbookIndex.from_path(
        repo_root() / "PINN报错诊断与模块选择手册.md"
    )
    rules = build_rules()
    concepts = build_concept_lexicon()
    return HybridRetrievalService(
        section_index=HybridSectionIndex.from_handbook(handbook_index, concepts),
        rules_service=RulesRetrievalService(handbook_index, rules),
        rules=rules,
        concepts=concepts,
    )


def create_product_server() -> StdioMcpServer:
    """Build the complete product server through its public composition root."""
    return create_server(repo_root())

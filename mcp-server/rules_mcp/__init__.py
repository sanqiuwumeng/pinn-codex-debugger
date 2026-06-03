"""Deterministic PINN handbook retrieval over a local MCP boundary."""

from .catalog import build_rules
from .handbook import HandbookIndex
from .service import RulesRetrievalService

__all__ = ["HandbookIndex", "RulesRetrievalService", "build_rules"]

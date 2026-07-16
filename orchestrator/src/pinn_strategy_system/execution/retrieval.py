"""Explicit read-only adapter for the existing deterministic MCP product."""

from __future__ import annotations

import json
from typing import Any, Protocol

from pinn_strategy_system.contracts import (
    EvidenceItem,
    RetrievalRequest,
    RetrievalResponse,
)

PROTOCOL_VERSION = "2025-11-25"
HYBRID_TOOL = "hybrid_search_pinn_handbook"


class McpMessageHandler(Protocol):
    def handle_message(self, raw_message: str) -> dict[str, Any] | None: ...


class RetrievalProvider(Protocol):
    def search(self, request: RetrievalRequest) -> RetrievalResponse: ...


class McpReadOnlyRetrievalProvider:
    """Call one fixed MCP search tool after verifying its safety annotations."""

    def __init__(
        self,
        handler: McpMessageHandler,
        *,
        source_uri: str,
    ) -> None:
        self._handler = handler
        self._source_uri = source_uri
        self._initialized = False

    def search(self, request: RetrievalRequest) -> RetrievalResponse:
        self._ensure_read_only_tool()
        response = self._request(
            3,
            "tools/call",
            {
                "name": HYBRID_TOOL,
                "arguments": {
                    "query": request.query,
                    "evidence": list(request.evidence),
                    "anchors": list(request.anchors),
                    "max_sections": request.max_sections,
                },
            },
        )
        result = _require_mapping(response.get("result"), "tools/call result")
        if result.get("isError") is not False:
            raise RuntimeError("MCP retrieval tool returned an error")
        payload = _require_mapping(
            result.get("structuredContent"),
            "structuredContent",
        )
        source_sha256 = _require_string(payload, "source_sha256").lower()
        ranked = payload.get("ranked_sections")
        if not isinstance(ranked, list):
            raise RuntimeError("ranked_sections must be an array")
        evidence = tuple(
            self._evidence_item(source_sha256, item)
            for item in ranked
        )
        return RetrievalResponse(
            request_id=request.request_id,
            provider="pinn-hybrid-rag-mcp",
            backend=_require_string(payload, "backend"),
            source_sha256=source_sha256,
            evidence=evidence,
            read_only=True,
        )

    def _ensure_read_only_tool(self) -> None:
        if self._initialized:
            return
        self._request(
            1,
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "pinn-strategy-orchestrator",
                    "version": "0.1.0",
                },
            },
        )
        notification = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
            ensure_ascii=False,
        )
        self._handler.handle_message(notification)
        tools_response = self._request(2, "tools/list", {})
        result = _require_mapping(tools_response.get("result"), "tools/list result")
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise RuntimeError("MCP tools/list did not return an array")
        definition = next(
            (
                item
                for item in tools
                if isinstance(item, dict) and item.get("name") == HYBRID_TOOL
            ),
            None,
        )
        if definition is None:
            raise RuntimeError(f"MCP tool is unavailable: {HYBRID_TOOL}")
        annotations = _require_mapping(
            definition.get("annotations"),
            "tool annotations",
        )
        if annotations.get("readOnlyHint") is not True:
            raise RuntimeError("MCP retrieval tool is not declared read-only")
        if annotations.get("destructiveHint") is not False:
            raise RuntimeError("MCP retrieval tool is not declared non-destructive")
        self._initialized = True

    def _request(
        self,
        request_id: int,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        raw = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            },
            ensure_ascii=False,
        )
        response = self._handler.handle_message(raw)
        if not isinstance(response, dict):
            raise RuntimeError(f"MCP {method} returned no response")
        if "error" in response:
            raise RuntimeError(f"MCP {method} failed: {response['error']}")
        return response

    def _evidence_item(
        self,
        source_sha256: str,
        raw_item: Any,
    ) -> EvidenceItem:
        item = _require_mapping(raw_item, "ranked section")
        metadata = _json_projection({
            key: value
            for key, value in item.items()
            if key
            not in {
                "heading",
                "line_start",
                "line_end",
                "excerpt",
                "score",
            }
        })
        return EvidenceItem(
            source_uri=self._source_uri,
            source_sha256=source_sha256,
            heading=_require_string(item, "heading"),
            line_start=_require_int(item, "line_start"),
            line_end=_require_int(item, "line_end"),
            excerpt=_require_string(item, "excerpt"),
            score=_require_number(item, "score"),
            metadata=metadata,
        )


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be an object")
    return value


def _require_string(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{name} must be a non-empty string")
    return value


def _require_int(payload: dict[str, Any], name: str) -> int:
    value = payload.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise RuntimeError(f"{name} must be an integer")
    return value


def _require_number(payload: dict[str, Any], name: str) -> float:
    value = payload.get(name)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise RuntimeError(f"{name} must be numeric")
    return float(value)


def _json_projection(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        projected = json.loads(
            json.dumps(payload, ensure_ascii=False, allow_nan=False)
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"MCP metadata is not JSON-serializable: {error}") from error
    if not isinstance(projected, dict):
        raise RuntimeError("MCP metadata projection must remain an object")
    return projected

"""Minimal stdio MCP server implemented with the Python standard library."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from .models import DiagnosisRequest, SearchRequest
from .service import RulesRetrievalService

PROTOCOL_VERSION = "2025-11-25"


class StdioMcpServer:
    """Handle newline-delimited UTF-8 MCP JSON-RPC messages."""

    def __init__(self, service: RulesRetrievalService) -> None:
        self._service = service
        self._initialize_completed = False
        self._initialized = False

    def run(self, input_stream: TextIO, output_stream: TextIO) -> None:
        for raw_line in input_stream:
            line = raw_line.strip()
            if not line:
                continue
            response = self.handle_message(line)
            if response is not None:
                output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
                output_stream.flush()

    def handle_message(self, raw_message: str) -> dict[str, Any] | None:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError as error:
            return _error_response(None, -32700, f"Parse error: {error.msg}")

        if not isinstance(message, dict):
            return _error_response(None, -32600, "Invalid Request")
        if message.get("jsonrpc") != "2.0":
            return _error_response(message.get("id"), -32600, "Invalid Request")

        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params", {})
        if not isinstance(method, str) or not isinstance(params, dict):
            return _error_response(request_id, -32600, "Invalid Request")

        if request_id is None:
            self._handle_notification(method)
            return None

        try:
            result = self._dispatch(method, params)
        except ValueError as error:
            return _error_response(request_id, -32602, str(error))
        except KeyError as error:
            return _error_response(request_id, -32601, str(error))
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _handle_notification(self, method: str) -> None:
        if method == "notifications/initialized" and self._initialize_completed:
            self._initialized = True

    def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            requested_version = params.get("protocolVersion")
            negotiated_version = (
                requested_version
                if requested_version == PROTOCOL_VERSION
                else PROTOCOL_VERSION
            )
            self._initialize_completed = True
            return {
                "protocolVersion": negotiated_version,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "pinn-rules-retrieval",
                    "title": "PINN Rules Retrieval",
                    "version": "0.1.0",
                    "description": (
                        "Deterministic PINN symptom routing and handbook evidence extraction."
                    ),
                },
                "instructions": (
                    "Use diagnose_pinn_symptom before recommending a PINN module. "
                    "Complete basic checks and change one logical point at a time."
                ),
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            self._require_initialized()
            return {"tools": tool_definitions()}
        if method == "tools/call":
            self._require_initialized()
            return self._call_tool(params)
        raise KeyError(f"Method not found: {method}")

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise ValueError(
                "Server initialization is incomplete; send initialize and "
                "notifications/initialized first"
            )

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise ValueError("tools/call requires a string name and object arguments")

        try:
            if name == "diagnose_pinn_symptom":
                payload = self._service.diagnose(
                    DiagnosisRequest.from_arguments(arguments)
                ).to_dict()
            elif name == "search_pinn_handbook":
                matches = self._service.search(SearchRequest.from_arguments(arguments))
                payload = {
                    "handbook_sha256": self._service.handbook_sha256,
                    "matches": [match.to_dict() for match in matches],
                }
            else:
                raise KeyError(f"Tool not found: {name}")
        except ValueError as error:
            return _tool_error(str(error))

        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        return {
            "content": [{"type": "text", "text": serialized}],
            "structuredContent": payload,
            "isError": False,
        }


def tool_definitions() -> list[dict[str, Any]]:
    """Return read-only MCP tool definitions with explicit schemas."""
    diagnosis_output = {
        "type": "object",
        "properties": {
            "symptom": {"type": "string"},
            "family": {"type": "string"},
            "matched_keywords": {"type": "array", "items": {"type": "string"}},
            "evidence_received": {"type": "array", "items": {"type": "string"}},
            "evidence_gaps": {"type": "array", "items": {"type": "string"}},
            "required_basic_checks": {"type": "array", "items": {"type": "string"}},
            "candidate_anchors": {"type": "array", "items": {"type": "string"}},
            "handbook_sha256": {"type": "string"},
            "handbook_matches": {"type": "array", "items": {"type": "object"}},
            "next_step_policy": {"type": "string"},
        },
        "required": [
            "symptom",
            "family",
            "matched_keywords",
            "evidence_received",
            "evidence_gaps",
            "required_basic_checks",
            "candidate_anchors",
            "handbook_sha256",
            "handbook_matches",
            "next_step_policy",
        ],
    }
    search_output = {
        "type": "object",
        "properties": {
            "handbook_sha256": {"type": "string"},
            "matches": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["handbook_sha256", "matches"],
    }
    return [
        {
            "name": "diagnose_pinn_symptom",
            "title": "Diagnose PINN Symptom",
            "description": (
                "Route an observable PINN symptom to one deterministic family, "
                "required basic checks, evidence gaps, and traceable handbook sections."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symptom": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "max_sections": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["symptom"],
                "additionalProperties": False,
            },
            "outputSchema": diagnosis_output,
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        },
        {
            "name": "search_pinn_handbook",
            "title": "Search PINN Handbook",
            "description": (
                "Extract exact handbook sections for explicit search terms or anchors "
                "with source hash and line-range provenance."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "anchors": {"type": "array", "items": {"type": "string"}},
                    "max_sections": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            "outputSchema": search_output,
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        },
    ]


def _tool_error(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def run_stdio_server(server: StdioMcpServer) -> None:
    """Run stdio using explicit UTF-8 wrappers configured by Python."""
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    server.run(sys.stdin, sys.stdout)

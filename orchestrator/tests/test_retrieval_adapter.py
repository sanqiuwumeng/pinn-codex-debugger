from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ORCHESTRATOR_SRC = Path(__file__).resolve().parents[1] / "src"
MCP_ROOT = Path(__file__).resolve().parents[2] / "mcp-server"
sys.path.insert(0, str(ORCHESTRATOR_SRC))
sys.path.insert(0, str(MCP_ROOT))

from pinn_strategy_system.contracts import RetrievalRequest  # noqa: E402
from pinn_strategy_system.execution import (  # noqa: E402
    McpReadOnlyRetrievalProvider,
)
from pinn_hybrid_rag.__main__ import create_server  # noqa: E402


class RecordingHandler:
    def __init__(self, delegate) -> None:
        self.delegate = delegate
        self.messages: list[dict] = []

    def handle_message(self, raw_message: str):
        self.messages.append(json.loads(raw_message))
        return self.delegate.handle_message(raw_message)


class UnsafeHandler:
    def handle_message(self, raw_message: str):
        message = json.loads(raw_message)
        if message.get("id") == 1:
            return {"jsonrpc": "2.0", "id": 1, "result": {}}
        if message.get("method") == "notifications/initialized":
            return None
        return {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [
                    {
                        "name": "hybrid_search_pinn_handbook",
                        "annotations": {
                            "readOnlyHint": False,
                            "destructiveHint": False,
                        },
                    }
                ]
            },
        }


class RetrievalAdapterTests(unittest.TestCase):
    def test_existing_mcp_is_called_through_read_only_versioned_provider(self) -> None:
        handler = RecordingHandler(create_server(MCP_ROOT.parent))
        provider = McpReadOnlyRetrievalProvider(
            handler,
            source_uri="file:///repo/PINN调试手册.md",
        )
        response = provider.search(
            RetrievalRequest(
                request_id="retrieval-1",
                project_id="project-1",
                query="局部残差热点持续存在，均匀加点没有改善。",
                max_sections=3,
            )
        )

        self.assertTrue(response.read_only)
        self.assertEqual(response.provider, "pinn-hybrid-rag-mcp")
        self.assertTrue(response.evidence)
        self.assertTrue(all(item.source_sha256 == response.source_sha256 for item in response.evidence))
        self.assertTrue(all(item.line_end >= item.line_start for item in response.evidence))
        methods = [message["method"] for message in handler.messages]
        self.assertEqual(
            methods,
            [
                "initialize",
                "notifications/initialized",
                "tools/list",
                "tools/call",
            ],
        )
        tool_call = handler.messages[-1]
        self.assertEqual(
            tool_call["params"]["name"],
            "hybrid_search_pinn_handbook",
        )

    def test_adapter_refuses_tool_without_read_only_annotation(self) -> None:
        provider = McpReadOnlyRetrievalProvider(
            UnsafeHandler(),
            source_uri="file:///repo/PINN调试手册.md",
        )
        with self.assertRaisesRegex(RuntimeError, "not declared read-only"):
            provider.search(
                RetrievalRequest(
                    request_id="retrieval-unsafe",
                    project_id="project-1",
                    query="test query",
                )
            )


if __name__ == "__main__":
    unittest.main()

"""Low-level MCP JSON-RPC regression tests."""

from __future__ import annotations

import json
import unittest

from rules_mcp.server import PROTOCOL_VERSION

from .support import create_product_server


def request(request_id: int, method: str, params: dict) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        },
        ensure_ascii=False,
    )


def initialize(server) -> None:
    server.handle_message(
        request(
            1,
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.1.0"},
            },
        )
    )
    server.handle_message(
        json.dumps(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
    )


class StdioMcpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = create_product_server()
        initialize(self.server)

    def test_initialize_declares_product_identity_and_tools(self) -> None:
        server = create_product_server()
        response = server.handle_message(
            request(
                1,
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "0.1.0"},
                },
            )
        )

        self.assertEqual(response["result"]["protocolVersion"], PROTOCOL_VERSION)
        self.assertEqual(response["result"]["capabilities"], {"tools": {}})
        self.assertEqual(response["result"]["serverInfo"]["name"], "pinn-hybrid-rag")

    def test_tools_are_rejected_before_initialization(self) -> None:
        server = create_product_server()
        response = server.handle_message(request(2, "tools/list", {}))

        self.assertEqual(response["error"]["code"], -32602)

    def test_tools_list_exposes_three_explicit_schemas(self) -> None:
        response = self.server.handle_message(request(2, "tools/list", {}))
        tools = response["result"]["tools"]

        self.assertEqual(
            [tool["name"] for tool in tools],
            [
                "hybrid_search_pinn_handbook",
                "diagnose_pinn_symptom",
                "search_pinn_handbook",
            ],
        )
        self.assertTrue(all("inputSchema" in tool for tool in tools))
        self.assertTrue(all("outputSchema" in tool for tool in tools))

    def test_hybrid_tool_returns_ranked_structured_content(self) -> None:
        response = self.server.handle_message(
            request(
                3,
                "tools/call",
                {
                    "name": "hybrid_search_pinn_handbook",
                    "arguments": {
                        "query": "局部残差热点持续存在，均匀加点没有改善。",
                        "max_sections": 3,
                    },
                },
            )
        )
        result = response["result"]

        self.assertFalse(result["isError"])
        self.assertEqual(
            result["structuredContent"]["inferred_family"],
            "localized sampling difficulty",
        )
        self.assertTrue(result["structuredContent"]["ranked_sections"])
        self.assertEqual(result["content"][0]["type"], "text")

    def test_invalid_tool_arguments_return_tool_error(self) -> None:
        response = self.server.handle_message(
            request(
                4,
                "tools/call",
                {
                    "name": "hybrid_search_pinn_handbook",
                    "arguments": {"query": ""},
                },
            )
        )

        self.assertTrue(response["result"]["isError"])


if __name__ == "__main__":
    unittest.main()

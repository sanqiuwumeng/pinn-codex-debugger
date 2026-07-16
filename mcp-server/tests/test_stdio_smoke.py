"""Subprocess smoke test for the product stdio MCP entrypoint."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from rules_mcp.server import PROTOCOL_VERSION


class StdioSmokeTests(unittest.TestCase):
    def test_product_stdio_round_trip(self) -> None:
        server_root = Path(__file__).resolve().parents[1]
        environment = dict(os.environ)
        environment["PYTHONUTF8"] = "1"
        requests = (
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "smoke-client", "version": "0.1.0"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "hybrid_search_pinn_handbook",
                    "arguments": {"query": "总质量随时间持续偏移。"},
                },
            },
        )
        input_text = "".join(
            json.dumps(payload, ensure_ascii=False) + "\n" for payload in requests
        )
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "pinn_hybrid_rag"],
            cwd=server_root,
            env=environment,
            text=True,
            encoding="utf-8",
            input=input_text,
            capture_output=True,
            check=True,
            timeout=5,
        )
        responses = [
            json.loads(line) for line in completed.stdout.splitlines() if line
        ]

        self.assertEqual(completed.stderr, "")
        self.assertEqual(len(responses), 3)
        self.assertEqual(responses[0]["result"]["protocolVersion"], PROTOCOL_VERSION)
        self.assertEqual(len(responses[1]["result"]["tools"]), 3)
        self.assertEqual(
            responses[2]["result"]["structuredContent"]["inferred_family"],
            "physical structure preservation",
        )


if __name__ == "__main__":
    unittest.main()

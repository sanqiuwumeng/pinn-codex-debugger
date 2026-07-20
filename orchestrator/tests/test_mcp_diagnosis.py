from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
MCP_ROOT = Path(__file__).resolve().parents[2] / "mcp-server"
HANDBOOK = MCP_ROOT.parent / "PINN报错诊断与模块选择手册.md"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.cli import main  # noqa: E402
from pinn_strategy_system.execution import StdioMcpRuntimeProfile  # noqa: E402


class McpDiagnosisTests(unittest.TestCase):
    def test_cli_calls_real_mcp_in_an_isolated_read_only_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            environment = {
                name: os.environ[name]
                for name in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP")
                if name in os.environ
            }
            environment.update(
                {
                    "PYTHONPATH": str(MCP_ROOT),
                    "PYTHONUTF8": "1",
                }
            )
            environment_path = root / "mcp-environment.json"
            environment_path.write_text(
                json.dumps(environment),
                encoding="utf-8",
            )
            profile = StdioMcpRuntimeProfile(
                executable=Path(sys.executable),
                arguments=("-m", "pinn_hybrid_rag"),
                working_directory=MCP_ROOT,
                environment_file=environment_path,
                source_uri=HANDBOOK.as_uri(),
                request_timeout_seconds=15,
            )
            profile_path = root / "mcp-profile.json"
            profile_path.write_text(
                profile.model_dump_json(indent=2),
                encoding="utf-8",
            )
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(
                    [
                        "diagnose",
                        "--runtime-root",
                        str(root / "runtime"),
                        "--project-id",
                        "project-mcp-test",
                        "--query",
                        "边界损失下降但局部最大误差仍在边界附近",
                        "--mcp-profile",
                        str(profile_path),
                        "--max-sections",
                        "3",
                        "--json",
                    ]
                )
            payload = json.loads(stream.getvalue())

            self.assertEqual(code, 0)
            self.assertEqual(payload["code"], "MCP_EVIDENCE_READY")
            retrieval = payload["data"]["retrieval"]
            self.assertTrue(retrieval["read_only"])
            self.assertEqual(retrieval["provider"], "pinn-hybrid-rag-mcp")
            self.assertGreater(len(retrieval["evidence"]), 0)
            self.assertLessEqual(len(retrieval["evidence"]), 3)
            self.assertTrue(
                all(item["source_sha256"] == retrieval["source_sha256"] for item in retrieval["evidence"])
            )
            self.assertFalse((root / "runtime" / "workflows").exists())


if __name__ == "__main__":
    unittest.main()

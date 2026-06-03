"""Smoke test for the installed or source-tree PINN Hybrid RAG entrypoint."""

from __future__ import annotations

import json

from pinn_hybrid_rag.__main__ import create_server


def _request(request_id: int, method: str, params: dict) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        },
        ensure_ascii=False,
    )


def main() -> None:
    server = create_server()
    initialize = server.handle_message(
        _request(1, "initialize", {"protocolVersion": "2025-11-25"})
    )
    server.handle_message(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
            ensure_ascii=False,
        )
    )
    tools = server.handle_message(_request(2, "tools/list", {}))
    result = server.handle_message(
        _request(
            3,
            "tools/call",
            {
                "name": "hybrid_search_pinn_handbook",
                "arguments": {
                    "query": "局部残差热点，早期时间界面误差明显，边界值正确",
                    "evidence": ["边界条件已通过检查"],
                    "max_sections": 3,
                },
            },
        )
    )

    if initialize is None or tools is None or result is None:
        raise AssertionError("MCP server returned an empty response")
    if "error" in initialize or "error" in tools or "error" in result:
        raise AssertionError("MCP server returned an error response")

    payload = result["result"]["structuredContent"]
    ranked_sections = payload["ranked_sections"]
    if not ranked_sections:
        raise AssertionError("hybrid_search_pinn_handbook returned no sections")

    summary = {
        "server": initialize["result"]["serverInfo"]["name"],
        "tools": [tool["name"] for tool in tools["result"]["tools"]],
        "hybrid_family": payload["inferred_family"],
        "ranked_count": len(ranked_sections),
        "top_heading": ranked_sections[0]["heading"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

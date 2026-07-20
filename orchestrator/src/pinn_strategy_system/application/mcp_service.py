"""Read-only MCP diagnosis application service."""

from __future__ import annotations

from pathlib import Path

from pinn_strategy_system.contracts import RetrievalRequest
from pinn_strategy_system.execution.mcp_process import (
    SubprocessMcpMessageHandler,
    load_mcp_runtime_profile,
)
from pinn_strategy_system.execution.retrieval import McpReadOnlyRetrievalProvider

from .contracts import ApplicationResult, OperationOutcome


class McpDiagnosisApplicationService:
    def diagnose(
        self,
        *,
        project_id: str,
        query: str,
        profile_path: Path,
        evidence: tuple[str, ...] = (),
        anchors: tuple[str, ...] = (),
        max_sections: int = 5,
    ) -> ApplicationResult:
        profile = load_mcp_runtime_profile(profile_path)
        request = RetrievalRequest(
            request_id=f"mcp-diagnosis-{project_id}",
            project_id=project_id,
            query=query,
            evidence=evidence,
            anchors=anchors,
            max_sections=max_sections,
        )
        with SubprocessMcpMessageHandler(profile) as handler:
            response = McpReadOnlyRetrievalProvider(
                handler,
                source_uri=profile.source_uri,
            ).search(request)
        return ApplicationResult(
            command="diagnose",
            outcome=OperationOutcome.SUCCESS,
            code="MCP_EVIDENCE_READY",
            message="Read-only MCP diagnosis evidence is ready.",
            data={"retrieval": response.model_dump(mode="json")},
        )

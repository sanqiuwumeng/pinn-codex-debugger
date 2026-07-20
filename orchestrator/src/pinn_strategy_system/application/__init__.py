"""Operator-facing application services with no CLI parsing concerns."""

from .catalog import SQLiteWorkflowCatalog
from .contracts import ApplicationResult, OperationOutcome, OperatorCase
from .mcp_service import McpDiagnosisApplicationService
from .post_run import (
    EvaluationEvidenceCandidate,
    FieldArtifactDescriptor,
    PostRunEvaluationContract,
    PostRunEvaluationService,
    load_post_run_contract,
)
from .project_adapter import (
    ProjectAdaptationReport,
    ProjectAdapterManifest,
    ProjectAdapterService,
    SourceFileRecord,
)
from .rag_service import RagApplicationService
from .runtime_profiles import (
    AutoDlExecutionRuntimeProfile,
    LocalExecutionRuntimeProfile,
    ModelProcessRoleProfile,
    RetrievalModelRuntimeProfile,
    SubprocessModelTransportFactory,
    load_execution_backend,
)
from .service import OperatorApplicationService

__all__ = [
    "ApplicationResult",
    "AutoDlExecutionRuntimeProfile",
    "EvaluationEvidenceCandidate",
    "FieldArtifactDescriptor",
    "LocalExecutionRuntimeProfile",
    "ModelProcessRoleProfile",
    "McpDiagnosisApplicationService",
    "OperationOutcome",
    "OperatorApplicationService",
    "OperatorCase",
    "ProjectAdaptationReport",
    "ProjectAdapterManifest",
    "ProjectAdapterService",
    "PostRunEvaluationContract",
    "PostRunEvaluationService",
    "RagApplicationService",
    "RetrievalModelRuntimeProfile",
    "SQLiteWorkflowCatalog",
    "SubprocessModelTransportFactory",
    "SourceFileRecord",
    "load_execution_backend",
    "load_post_run_contract",
]

"""Read-only execution services and explicit external adapters."""

from .autodl_ssh import AutoDlSshBackendConfig, AutoDlSshRunnerBackend
from .local_process import LocalProcessBackendConfig, LocalProcessRunnerBackend
from .prediction import FieldData, PredictionAnalyzer
from .process_monitor import (
    ApprovedProcessIdentity,
    ApprovedProcessSampler,
    ProcessUnavailableError,
)
from .retrieval import McpReadOnlyRetrievalProvider, RetrievalProvider
from .runner import (
    ExecutionBackend,
    IdempotencyConflictError,
    ManifestFirstRunner,
    RunLaunchUncertainError,
    RunPreparationError,
    RunRegistrySchemaError,
    SQLiteRunRegistry,
)
from .ssh_transport import (
    AutoDlTransport,
    SshTransportError,
    SystemOpenSshRuntime,
    SystemOpenSshTransport,
)

__all__ = [
    "FieldData",
    "ApprovedProcessIdentity",
    "ApprovedProcessSampler",
    "AutoDlSshBackendConfig",
    "AutoDlSshRunnerBackend",
    "AutoDlTransport",
    "ExecutionBackend",
    "IdempotencyConflictError",
    "LocalProcessBackendConfig",
    "LocalProcessRunnerBackend",
    "ManifestFirstRunner",
    "McpReadOnlyRetrievalProvider",
    "PredictionAnalyzer",
    "ProcessUnavailableError",
    "RetrievalProvider",
    "RunLaunchUncertainError",
    "RunPreparationError",
    "RunRegistrySchemaError",
    "SQLiteRunRegistry",
    "SshTransportError",
    "SystemOpenSshRuntime",
    "SystemOpenSshTransport",
]

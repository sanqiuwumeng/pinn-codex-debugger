"""Transient backend and model-runtime profiles loaded at composition time."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import Field, model_validator

from pinn_strategy_system.contracts import SshConnectionProfile, VersionedModel
from pinn_strategy_system.execution import (
    AutoDlSshBackendConfig,
    AutoDlSshRunnerBackend,
    ExecutionBackend,
    LocalProcessBackendConfig,
    LocalProcessRunnerBackend,
    SystemOpenSshRuntime,
    SystemOpenSshTransport,
)
from pinn_strategy_system.retrieval import SubprocessJsonlModelTransport


class LocalExecutionRuntimeProfile(VersionedModel):
    backend: Literal["local-process"] = "local-process"
    run_root: Path
    launcher_interpreter: Path
    environment_file: Path
    environment_allowlist: tuple[str, ...] = Field(min_length=1)
    heartbeat_interval_seconds: float = Field(default=0.5, gt=0)
    heartbeat_stale_after_seconds: float = Field(default=5.0, gt=0)
    cancellation_timeout_seconds: float = Field(default=5.0, gt=0)

    @model_validator(mode="after")
    def paths_are_absolute(self) -> Self:
        _require_absolute_paths(
            self.run_root,
            self.launcher_interpreter,
            self.environment_file,
        )
        return self


class AutoDlExecutionRuntimeProfile(VersionedModel):
    backend: Literal["autodl-ssh"] = "autodl-ssh"
    connection_profile: SshConnectionProfile
    remote_root: str = Field(pattern=r"^/[^\r\n\x00]*$")
    local_control_root: Path
    remote_environment: dict[str, str] = Field(min_length=1)
    environment_allowlist: tuple[str, ...] = Field(min_length=1)
    ssh_executable: Path
    scp_executable: Path
    username: str = Field(min_length=1, max_length=256, repr=False)
    hostname: str = Field(min_length=1, max_length=253, repr=False)
    port: int = Field(ge=1, le=65535, repr=False)
    identity_file: Path = Field(repr=False)
    known_hosts_file: Path
    remote_python: str = Field(pattern=r"^/[^\r\n\x00]*$")
    local_working_directory: Path
    local_environment_file: Path = Field(repr=False)
    connect_timeout_seconds: int = Field(default=15, gt=0)
    operation_timeout_seconds: int = Field(default=120, gt=0)
    heartbeat_interval_seconds: float = Field(default=1.0, gt=0)
    heartbeat_stale_after_seconds: float = Field(default=15.0, gt=0)

    @model_validator(mode="after")
    def paths_are_absolute(self) -> Self:
        _require_absolute_paths(
            self.local_control_root,
            self.ssh_executable,
            self.scp_executable,
            self.identity_file,
            self.known_hosts_file,
            self.local_working_directory,
            self.local_environment_file,
        )
        return self


class ModelProcessRoleProfile(VersionedModel):
    executable: Path = Field(repr=False)
    arguments: tuple[str, ...] = Field(min_length=1, repr=False)
    working_directory: Path
    environment_file: Path = Field(repr=False)
    timeout_seconds: float = Field(default=300.0, gt=0)
    max_request_bytes: int = Field(default=8 * 1024 * 1024, ge=1)
    max_response_bytes: int = Field(default=64 * 1024 * 1024, ge=1)

    @model_validator(mode="after")
    def paths_are_absolute(self) -> Self:
        _require_absolute_paths(
            self.executable,
            self.working_directory,
            self.environment_file,
        )
        return self


class RetrievalModelRuntimeProfile(VersionedModel):
    embedding: ModelProcessRoleProfile
    reranker: ModelProcessRoleProfile


def load_execution_backend(profile_path: Path) -> ExecutionBackend:
    payload = _read_json_object(profile_path)
    backend = payload.get("backend")
    if backend == "local-process":
        profile = LocalExecutionRuntimeProfile.model_validate(payload)
        environment = _environment(profile.environment_file)
        return LocalProcessRunnerBackend(
            LocalProcessBackendConfig(
                run_root=profile.run_root.resolve(strict=True),
                launcher_interpreter=profile.launcher_interpreter.resolve(
                    strict=True
                ),
                environment=environment,
                environment_allowlist=profile.environment_allowlist,
                heartbeat_interval_seconds=profile.heartbeat_interval_seconds,
                heartbeat_stale_after_seconds=(
                    profile.heartbeat_stale_after_seconds
                ),
                cancellation_timeout_seconds=(
                    profile.cancellation_timeout_seconds
                ),
            )
        )
    if backend == "autodl-ssh":
        profile = AutoDlExecutionRuntimeProfile.model_validate(payload)
        local_environment = _environment(profile.local_environment_file)
        runtime = SystemOpenSshRuntime(
            profile_id=profile.connection_profile.profile_id,
            ssh_executable=profile.ssh_executable.resolve(strict=True),
            scp_executable=profile.scp_executable.resolve(strict=True),
            username=profile.username,
            hostname=profile.hostname,
            port=profile.port,
            identity_file=profile.identity_file.resolve(strict=True),
            known_hosts_file=profile.known_hosts_file.resolve(strict=True),
            remote_python=PurePosixPath(profile.remote_python),
            local_working_directory=profile.local_working_directory.resolve(
                strict=True
            ),
            environment=local_environment,
            connect_timeout_seconds=profile.connect_timeout_seconds,
            operation_timeout_seconds=profile.operation_timeout_seconds,
        )
        config = AutoDlSshBackendConfig(
            connection_profile=profile.connection_profile,
            remote_root=PurePosixPath(profile.remote_root),
            local_control_root=profile.local_control_root.resolve(strict=True),
            remote_environment=tuple(sorted(profile.remote_environment.items())),
            environment_allowlist=profile.environment_allowlist,
            heartbeat_interval_seconds=profile.heartbeat_interval_seconds,
            heartbeat_stale_after_seconds=(
                profile.heartbeat_stale_after_seconds
            ),
        )
        return AutoDlSshRunnerBackend(config, SystemOpenSshTransport(runtime))
    raise ValueError("execution runtime profile backend is unsupported")


class SubprocessModelTransportFactory:
    def __init__(self, profile_path: Path) -> None:
        self._profile = RetrievalModelRuntimeProfile.model_validate(
            _read_json_object(profile_path)
        )

    def __call__(self, role: str) -> SubprocessJsonlModelTransport:
        profile = {
            "embedding": self._profile.embedding,
            "reranker": self._profile.reranker,
        }.get(role)
        if profile is None:
            raise ValueError("model runtime role is unsupported")
        return SubprocessJsonlModelTransport(
            executable=profile.executable.resolve(strict=True),
            arguments=profile.arguments,
            working_directory=profile.working_directory.resolve(strict=True),
            environment=_environment(profile.environment_file),
            timeout_seconds=profile.timeout_seconds,
            max_request_bytes=profile.max_request_bytes,
            max_response_bytes=profile.max_response_bytes,
        )


def _read_json_object(path: Path) -> dict:
    if not path.is_absolute() or not path.is_file():
        raise ValueError("runtime profile must be an existing absolute file")
    if path.stat().st_size > 1_048_576:
        raise ValueError("runtime profile exceeds the 1 MiB limit")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("runtime profile must be a JSON object")
    return payload


def _environment(path: Path) -> tuple[tuple[str, str], ...]:
    payload = _read_json_object(path)
    if not all(isinstance(name, str) and isinstance(value, str) for name, value in payload.items()):
        raise ValueError("runtime environment must contain string entries")
    names = tuple(name.casefold() for name in payload)
    if len(names) != len(set(names)):
        raise ValueError("runtime environment names must be unique")
    return tuple(payload.items())


def _require_absolute_paths(*paths: Path) -> None:
    if any(not path.is_absolute() for path in paths):
        raise ValueError("runtime profile paths must be absolute")

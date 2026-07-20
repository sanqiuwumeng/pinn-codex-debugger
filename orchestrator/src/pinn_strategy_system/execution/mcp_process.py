"""Explicit stdio process transport for the read-only MCP adapter."""

from __future__ import annotations

import json
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any, Self

from pydantic import Field, model_validator

from pinn_strategy_system.contracts import VersionedModel


class StdioMcpRuntimeProfile(VersionedModel):
    executable: Path
    arguments: tuple[str, ...] = ()
    working_directory: Path
    environment_file: Path
    source_uri: str = Field(min_length=1, max_length=4096)
    request_timeout_seconds: float = Field(default=15.0, gt=0, le=120)

    @model_validator(mode="after")
    def paths_are_absolute(self) -> Self:
        paths = (
            self.executable,
            self.working_directory,
            self.environment_file,
        )
        if any(not path.is_absolute() for path in paths):
            raise ValueError("MCP runtime profile paths must be absolute")
        return self


class SubprocessMcpMessageHandler:
    """Maintain one bounded MCP JSON-RPC session with no shell invocation."""

    def __init__(self, profile: StdioMcpRuntimeProfile) -> None:
        if not profile.executable.is_file():
            raise ValueError("MCP executable does not exist")
        if not profile.working_directory.is_dir():
            raise ValueError("MCP working_directory does not exist")
        environment = _load_environment(profile.environment_file)
        self._timeout = profile.request_timeout_seconds
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._process = subprocess.Popen(
            [str(profile.executable), *profile.arguments],
            cwd=profile.working_directory,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="strict",
            bufsize=1,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._reader = threading.Thread(
            target=self._read_stdout,
            name="pinn-strategy-mcp-reader",
            daemon=True,
        )
        self._reader.start()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def handle_message(self, raw_message: str) -> dict[str, Any] | None:
        if self._process.poll() is not None:
            raise RuntimeError("MCP process is not running")
        stdin = self._process.stdin
        if stdin is None:
            raise RuntimeError("MCP process input is unavailable")
        message = _json_object(raw_message, "MCP request")
        stdin.write(raw_message.rstrip("\r\n") + "\n")
        stdin.flush()
        if message.get("id") is None:
            return None
        try:
            response_line = self._responses.get(timeout=self._timeout)
        except queue.Empty as error:
            raise TimeoutError("MCP response timed out") from error
        if response_line is None:
            raise RuntimeError("MCP process ended before returning a response")
        return _json_object(response_line, "MCP response")

    def close(self) -> None:
        if self._process.poll() is None:
            if self._process.stdin is not None:
                self._process.stdin.close()
            try:
                self._process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._process.terminate()
                try:
                    self._process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=1.0)
        self._reader.join(timeout=1.0)
        if self._process.stdout is not None:
            self._process.stdout.close()

    def _read_stdout(self) -> None:
        stdout = self._process.stdout
        if stdout is None:
            self._responses.put(None)
            return
        try:
            for line in stdout:
                self._responses.put(line)
        finally:
            self._responses.put(None)


def load_mcp_runtime_profile(path: Path) -> StdioMcpRuntimeProfile:
    if not path.is_absolute() or not path.is_file():
        raise ValueError("MCP runtime profile must be an existing absolute file")
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("MCP runtime profile exceeds the 1 MiB limit")
    return StdioMcpRuntimeProfile.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def _load_environment(path: Path) -> dict[str, str]:
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("MCP environment file is missing or too large")
    payload = _json_object(path.read_text(encoding="utf-8"), "MCP environment")
    if not all(
        isinstance(name, str) and name and isinstance(value, str)
        for name, value in payload.items()
    ):
        raise ValueError("MCP environment must map non-empty names to strings")
    return {str(name): str(value) for name, value in payload.items()}


def _json_object(raw: str, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{label} is not valid JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return payload

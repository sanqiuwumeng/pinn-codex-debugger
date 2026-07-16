"""Explicit system-OpenSSH transport with credential-safe failures."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol


_ENSURE_DIRECTORY_SCRIPT = """\
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.mkdir(parents=True, exist_ok=True)
print(json.dumps({"status": "ready"}, sort_keys=True))
"""


_INSTALL_CONTENT_SCRIPT = """\
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


source = Path(sys.argv[1])
destination = Path(sys.argv[2])
expected = sys.argv[3]
if sha256(source) != expected:
    raise RuntimeError("uploaded content hash mismatch")
destination.parent.mkdir(parents=True, exist_ok=True)
if destination.exists() and sha256(destination) == expected:
    source.unlink()
    print(json.dumps({"status": "reused", "sha256": expected}, sort_keys=True))
    raise SystemExit(0)
if destination.exists():
    now = datetime.now(timezone.utc)
    backup_root = destination.parent / (
        "backups_install_" + now.strftime("%Y%m%d_%H%M%S")
    )
    backup_root.mkdir(parents=True, exist_ok=False)
    backup = backup_root / (
        destination.name + "_backup_" + now.strftime("%Y-%m-%d")
    )
    shutil.copy2(destination, backup)
os.replace(source, destination)
print(json.dumps({"status": "installed", "sha256": expected}, sort_keys=True))
"""


class SshTransportError(RuntimeError):
    """Sanitized transport failure that never embeds endpoint or command data."""


@dataclass(frozen=True, repr=False)
class SystemOpenSshRuntime:
    profile_id: str
    ssh_executable: Path
    scp_executable: Path
    username: str
    hostname: str
    port: int
    identity_file: Path
    known_hosts_file: Path
    remote_python: PurePosixPath
    local_working_directory: Path
    environment: tuple[tuple[str, str], ...]
    connect_timeout_seconds: int = 15
    operation_timeout_seconds: int = 120

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,256}", self.profile_id):
            raise ValueError("SSH profile_id contains unsupported characters")
        for executable in (self.ssh_executable, self.scp_executable):
            if not executable.is_absolute() or not executable.is_file():
                raise ValueError("OpenSSH executable must be an existing absolute file")
        for path in (self.identity_file, self.known_hosts_file):
            if not path.is_absolute() or not path.is_file():
                raise ValueError("SSH identity and known-hosts paths must exist")
        if not self.local_working_directory.is_absolute():
            raise ValueError("SSH local working directory must be absolute")
        if not self.local_working_directory.is_dir():
            raise ValueError("SSH local working directory must exist")
        if not self.remote_python.is_absolute():
            raise ValueError("remote Python path must be absolute")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,256}", self.username):
            raise ValueError("SSH username contains unsupported characters")
        if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", self.hostname):
            raise ValueError("SSH hostname contains unsupported characters")
        if not 1 <= self.port <= 65535:
            raise ValueError("SSH port is outside the valid range")
        names = tuple(name.casefold() for name, _ in self.environment)
        if len(names) != len(set(names)):
            raise ValueError("SSH environment names must be unique")
        if self.connect_timeout_seconds <= 0:
            raise ValueError("SSH connect timeout must be positive")
        if self.operation_timeout_seconds <= 0:
            raise ValueError("SSH operation timeout must be positive")

    def __repr__(self) -> str:
        return (
            "SystemOpenSshRuntime("
            f"profile_id={self.profile_id!r}, endpoint=<redacted>)"
        )

    def environment_dict(self) -> dict[str, str]:
        return dict(self.environment)


class AutoDlTransport(Protocol):
    def ensure_directory(self, remote_path: PurePosixPath) -> None: ...

    def install_content(
        self,
        local_path: Path,
        remote_path: PurePosixPath,
        sha256: str,
    ) -> None: ...

    def invoke(
        self,
        worker_path: PurePosixPath,
        arguments: tuple[str, ...],
    ) -> dict: ...

    def download(self, remote_path: PurePosixPath, local_path: Path) -> None: ...


class SystemOpenSshTransport:
    def __init__(self, runtime: SystemOpenSshRuntime) -> None:
        self._runtime = runtime

    def ensure_directory(self, remote_path: PurePosixPath) -> None:
        _validate_remote_path(remote_path)
        self._invoke_inline(_ENSURE_DIRECTORY_SCRIPT, (str(remote_path),))

    def install_content(
        self,
        local_path: Path,
        remote_path: PurePosixPath,
        sha256: str,
    ) -> None:
        source = local_path.resolve(strict=True)
        _validate_remote_path(remote_path)
        _validate_sha256(sha256)
        if _sha256(source) != sha256:
            raise ValueError("local content does not match declared SHA-256")
        self.ensure_directory(remote_path.parent)
        temporary = remote_path.with_name(
            f".{remote_path.name}.upload-{uuid.uuid4().hex}"
        )
        self._scp_upload(source, temporary)
        response = self._invoke_inline(
            _INSTALL_CONTENT_SCRIPT,
            (str(temporary), str(remote_path), sha256),
        )
        if response.get("sha256") != sha256:
            raise SshTransportError("remote content installation was not verified")

    def invoke(
        self,
        worker_path: PurePosixPath,
        arguments: tuple[str, ...],
    ) -> dict:
        _validate_remote_path(worker_path)
        _validate_remote_arguments(arguments)
        command = (
            str(self._runtime.remote_python),
            str(worker_path),
            *arguments,
        )
        completed = self._run_ssh(command)
        return _parse_json_response(completed.stdout)

    def download(self, remote_path: PurePosixPath, local_path: Path) -> None:
        _validate_remote_path(remote_path)
        destination = local_path
        if not destination.is_absolute() or not destination.parent.is_dir():
            raise ValueError(
                "download destination parent must be an absolute directory"
            )
        if destination.exists():
            raise FileExistsError("download destination already exists")
        command = (
            str(self._runtime.scp_executable),
            *self._scp_options(),
            f"{self._endpoint()}:{remote_path}",
            str(destination),
        )
        self._run_local(command)

    def _invoke_inline(
        self,
        script: str,
        arguments: tuple[str, ...],
    ) -> dict:
        _validate_remote_arguments(arguments)
        command = (
            str(self._runtime.remote_python),
            "-c",
            script,
            *arguments,
        )
        completed = self._run_ssh(command)
        return _parse_json_response(completed.stdout)

    def _scp_upload(
        self,
        local_path: Path,
        remote_path: PurePosixPath,
    ) -> None:
        command = (
            str(self._runtime.scp_executable),
            *self._scp_options(),
            str(local_path),
            f"{self._endpoint()}:{remote_path}",
        )
        self._run_local(command)

    def _run_ssh(
        self,
        remote_arguments: tuple[str, ...],
    ) -> subprocess.CompletedProcess:
        remote_command = shlex.join(remote_arguments)
        command = (
            str(self._runtime.ssh_executable),
            *self._ssh_options(),
            self._endpoint(),
            "--",
            remote_command,
        )
        return self._run_local(command)

    def _run_local(self, command: tuple[str, ...]) -> subprocess.CompletedProcess:
        try:
            completed = subprocess.run(
                command,
                cwd=self._runtime.local_working_directory,
                env=self._runtime.environment_dict(),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._runtime.operation_timeout_seconds,
                check=False,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, "CREATE_NO_WINDOW")
                    else 0
                ),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SshTransportError(
                f"OpenSSH transport failed: {type(error).__name__}"
            ) from None
        if completed.returncode != 0:
            raise SshTransportError(
                f"OpenSSH transport returned exit code {completed.returncode}"
            )
        return completed

    def _ssh_options(self) -> tuple[str, ...]:
        return (
            "-o",
            "BatchMode=yes",
            "-o",
            "PasswordAuthentication=no",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={self._runtime.known_hosts_file}",
            "-o",
            f"ConnectTimeout={self._runtime.connect_timeout_seconds}",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=2",
            "-i",
            str(self._runtime.identity_file),
            "-p",
            str(self._runtime.port),
        )

    def _scp_options(self) -> tuple[str, ...]:
        ssh_options = self._ssh_options()
        converted: list[str] = []
        index = 0
        while index < len(ssh_options):
            value = ssh_options[index]
            if value == "-p":
                converted.extend(("-P", ssh_options[index + 1]))
                index += 2
                continue
            converted.append(value)
            index += 1
        return tuple(converted)

    def _endpoint(self) -> str:
        return f"{self._runtime.username}@{self._runtime.hostname}"


def _parse_json_response(stdout: str) -> dict:
    encoded = stdout.strip()
    if not encoded:
        raise SshTransportError("remote operation returned no structured response")
    try:
        payload = json.loads(encoded)
    except json.JSONDecodeError:
        raise SshTransportError("remote operation returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise SshTransportError("remote operation response must be a JSON object")
    return payload


def _validate_remote_arguments(arguments: tuple[str, ...]) -> None:
    if any("\x00" in value or "\n" in value or "\r" in value for value in arguments):
        raise ValueError("remote argument contains a forbidden control character")


def _validate_remote_path(path: PurePosixPath) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("remote path must be absolute and confined")
    if any("\n" in part or "\r" in part or "\x00" in part for part in path.parts):
        raise ValueError("remote path contains a forbidden control character")


def _validate_sha256(value: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("SHA-256 value must be lowercase hexadecimal")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

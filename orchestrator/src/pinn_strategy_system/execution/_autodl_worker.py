"""Dependency-free durable worker installed on an AutoDL Linux instance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import tarfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any


TERMINAL_PHASES = ("COMPLETED", "FAILED", "CANCELLED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "operation",
        choices=("prepare", "launch", "run", "status", "cancel", "collect"),
    )
    parser.add_argument("--payload")
    parser.add_argument("--run-root")
    arguments = parser.parse_args()
    operation = arguments.operation
    if operation == "prepare":
        response = _prepare(_required_path(arguments.payload))
    else:
        run_root = _required_path(arguments.run_root).resolve(strict=True)
        if operation == "launch":
            response = _launch(run_root)
        elif operation == "run":
            return _run(run_root)
        elif operation == "status":
            response = _status_response(run_root)
        elif operation == "cancel":
            response = _cancel(run_root, _required_path(arguments.payload))
        else:
            response = _collect(run_root, _required_path(arguments.payload))
    print(_canonical_json(response), end="")
    return 0


def _prepare(payload_path: Path) -> dict[str, Any]:
    payload_path = payload_path.resolve(strict=True)
    payload = _read_json(payload_path)
    remote_root = Path(payload["remote_root"]).resolve(strict=True)
    run_root = _confined(Path(payload["run_root"]), remote_root)
    archive = _confined(
        Path(payload["staging_archive"]).resolve(strict=True),
        remote_root,
    )
    if _sha256(archive) != payload["staging_archive_sha256"]:
        raise RuntimeError("staging archive hash mismatch")
    request_path = run_root / "execution-request.json"
    if run_root.exists():
        if not run_root.is_dir() or not request_path.is_file():
            raise FileExistsError("remote run root already exists without a request")
        _write_or_verify(request_path, payload)
    else:
        run_root.mkdir(parents=True, exist_ok=False)
        _write_json_exclusive(request_path, payload)
    (run_root / "status-events").mkdir(exist_ok=True)
    (run_root / "heartbeats").mkdir(exist_ok=True)
    workspace = _confined(Path(payload["working_directory"]), run_root)
    if workspace != run_root / "workspace":
        raise ValueError("remote working directory must be the run workspace")
    if not workspace.exists():
        temporary = run_root / f".workspace.install-{uuid.uuid4().hex}"
        temporary.mkdir()
        _extract_safe_archive(archive, temporary)
        os.replace(temporary, workspace)
    launch_payload = {
        "run_id": payload["run_id"],
        "command": payload["command"],
        "interpreter": payload["interpreter"],
        "working_directory": payload["working_directory"],
        "output_root": payload["output_root"],
        "expected_artifacts": payload["expected_artifacts"],
        "environment": payload["environment"],
        "heartbeat_interval_seconds": payload["heartbeat_interval_seconds"],
        "heartbeat_stale_after_seconds": payload[
            "heartbeat_stale_after_seconds"
        ],
    }
    _validate_launch_payload(launch_payload, run_root)
    _write_or_verify(run_root / "launch-payload.json", launch_payload)
    return {
        "status": "prepared",
        "run_id": payload["run_id"],
        "staging_archive_sha256": payload["staging_archive_sha256"],
    }


def _launch(run_root: Path) -> dict[str, Any]:
    launcher_identity_path = run_root / "launcher-identity.json"
    if launcher_identity_path.exists():
        identity = _read_identity(launcher_identity_path)
        event = _latest_json(run_root / "status-events")
        if _identity_is_live(identity) or (
            event is not None and event.get("phase") in TERMINAL_PHASES
        ):
            return {
                "status": "reused",
                "launcher_identity": identity,
            }
        raise RuntimeError("launcher identity exists but outcome is uncertain")
    worker = Path(__file__).resolve(strict=True)
    environment = _worker_environment(run_root / "launch-payload.json")
    process = subprocess.Popen(
        (
            sys.executable,
            str(worker),
            "run",
            "--run-root",
            str(run_root),
        ),
        cwd=run_root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    identity = _process_identity(process.pid)
    _write_json_exclusive(launcher_identity_path, identity)
    return {"status": "launched", "launcher_identity": identity}


def _run(run_root: Path) -> int:
    payload = _read_json(run_root / "launch-payload.json")
    _validate_launch_payload(payload, run_root)
    status_root = run_root / "status-events"
    heartbeat_root = run_root / "heartbeats"
    _write_event(status_root, "starting", _status_event("PREPARED"))
    try:
        with (run_root / "stdout.log").open("xb") as stdout_stream, (
            run_root / "stderr.log"
        ).open("xb") as stderr_stream:
            process = subprocess.Popen(
                tuple(payload["command"]),
                cwd=payload["working_directory"],
                env=dict(payload["environment"]),
                stdin=subprocess.DEVNULL,
                stdout=stdout_stream,
                stderr=stderr_stream,
                start_new_session=True,
            )
            identity = _process_identity(process.pid)
            _write_json_exclusive(run_root / "process-identity.json", identity)
            _write_event(
                status_root,
                "running",
                _status_event("RUNNING", process_id=process.pid),
            )
            interval = float(payload["heartbeat_interval_seconds"])
            while process.poll() is None:
                _write_event(
                    heartbeat_root,
                    "heartbeat",
                    {"observed_at": _now(), "process_id": process.pid},
                )
                time.sleep(interval)
            exit_code = int(process.wait())
        if (run_root / "cancellation-approval.json").is_file():
            phase = "CANCELLED"
        else:
            phase = "COMPLETED" if exit_code == 0 else "FAILED"
        _write_event(
            status_root,
            phase.casefold(),
            _status_event(
                phase,
                process_id=process.pid,
                exit_code=exit_code,
            ),
        )
        return exit_code
    except BaseException as error:
        _write_event(
            status_root,
            "worker-failed",
            _status_event(
                "FAILED",
                detail=f"remote worker failed: {type(error).__name__}",
            ),
        )
        raise


def _status_response(run_root: Path) -> dict[str, Any]:
    payload = _read_json(run_root / "launch-payload.json")
    event = _latest_json(run_root / "status-events")
    target_identity = _read_identity_optional(run_root / "process-identity.json")
    identity = target_identity or _read_identity_optional(
        run_root / "launcher-identity.json"
    )
    process_matches = _identity_is_live(identity)
    produced = _produced_artifacts(payload)
    missing = tuple(
        name for name in payload["expected_artifacts"] if name not in produced
    )
    heartbeat = _latest_json(run_root / "heartbeats")
    phase, detail = _reconciled_phase(
        event,
        process_matches=process_matches,
        missing=missing,
        heartbeat=heartbeat,
        stale_after=float(payload["heartbeat_stale_after_seconds"]),
    )
    return {
        "phase": phase,
        "observed_at": _now(),
        "process_identity": identity,
        "target_identity_recorded": target_identity is not None,
        "exit_code": None if event is None else event.get("exit_code"),
        "heartbeat_at": None if heartbeat is None else heartbeat["observed_at"],
        "stdout_offset": _size_or_zero(run_root / "stdout.log"),
        "stderr_offset": _size_or_zero(run_root / "stderr.log"),
        "produced_artifacts": list(produced),
        "missing_artifacts": list(missing),
        "status_event_valid": event is not None,
        "detail": detail,
    }


def _cancel(run_root: Path, payload_path: Path) -> dict[str, Any]:
    request = _read_json(payload_path.resolve(strict=True))
    launch_payload = _read_json(run_root / "launch-payload.json")
    run_id = launch_payload["run_id"]
    if request.get("run_id") != run_id:
        raise ValueError("cancellation run_id mismatch")
    approval = request.get("approval", {})
    if approval.get("scope") != f"run:{run_id}:cancel":
        raise ValueError("cancellation approval scope mismatch")
    if approval.get("decision") != "APPROVED":
        raise ValueError("cancellation approval is not approved")
    _write_or_verify(run_root / "cancellation-approval.json", request)
    identities = tuple(
        identity
        for identity in (
            _read_identity_optional(run_root / "process-identity.json"),
            _read_identity_optional(run_root / "launcher-identity.json"),
        )
        if identity is not None
    )
    for identity in identities:
        _terminate_exact_tree(identity, timeout_seconds=10.0)
    still_live = any(_identity_is_live(identity) for identity in identities)
    stop_confirmed = bool(identities) and not still_live
    phase = "CANCELLED" if stop_confirmed else "RUNNING_UNKNOWN"
    _write_event(
        run_root / "status-events",
        "cancelled" if stop_confirmed else "cancel-uncertain",
        _status_event(phase, detail=request.get("reason")),
    )
    return _status_response(run_root)


def _collect(run_root: Path, payload_path: Path) -> dict[str, Any]:
    request = _read_json(payload_path.resolve(strict=True))
    launch_payload = _read_json(run_root / "launch-payload.json")
    if request.get("run_id") != launch_payload["run_id"]:
        raise ValueError("collection run_id mismatch")
    required = tuple(request.get("required_artifacts", ()))
    if required != tuple(launch_payload["expected_artifacts"]):
        raise ValueError("collection must request the declared artifact set")
    status = _status_response(run_root)
    if status["phase"] != "COMPLETED":
        raise RuntimeError("remote collection requires a completed run")
    output_root = Path(launch_payload["output_root"]).resolve(strict=True)
    entries, missing = _source_entries(output_root, required)
    source_manifest = run_root / "collection-source-manifest.json"
    source_payload = {
        "run_id": launch_payload["run_id"],
        "output_root": str(output_root),
        "entries": entries,
        "missing": list(missing),
    }
    _write_or_verify(source_manifest, source_payload)
    source_sha = _sha256(source_manifest)
    if missing:
        return {
            "status": "PARTIAL",
            "source_manifest_sha256": source_sha,
            "missing_artifacts": list(missing),
        }
    collection_root = run_root / "collections"
    collection_root.mkdir(exist_ok=True)
    archive = collection_root / f"artifacts-{source_sha}.tar"
    if not archive.exists():
        temporary = collection_root / f".{archive.name}.{uuid.uuid4().hex}.tmp"
        try:
            with tarfile.open(temporary, mode="x") as stream:
                stream.add(source_manifest, arcname="source-manifest.json")
                for entry in entries:
                    relative = _safe_relative(entry["relative_path"])
                    stream.add(
                        output_root / relative,
                        arcname=str(PurePosixPath("artifacts") / relative),
                    )
            os.link(temporary, archive)
        finally:
            temporary.unlink(missing_ok=True)
    return {
        "status": "COMPLETE",
        "archive_path": str(archive),
        "archive_sha256": _sha256(archive),
        "archive_size_bytes": archive.stat().st_size,
        "source_manifest_sha256": source_sha,
        "entries": entries,
        "missing_artifacts": [],
    }


def _validate_launch_payload(payload: dict[str, Any], run_root: Path) -> None:
    interpreter = Path(payload["interpreter"])
    working_directory = _confined(Path(payload["working_directory"]), run_root)
    output_root = _confined(Path(payload["output_root"]), working_directory)
    command = tuple(payload["command"])
    if (
        not interpreter.is_absolute()
        or not interpreter.is_file()
        or command[0] != str(interpreter)
    ):
        raise ValueError("remote command must start with the absolute interpreter")
    if working_directory != run_root / "workspace":
        raise ValueError("remote working directory must match the staged workspace")
    if output_root == working_directory:
        raise ValueError("remote output root must be below the workspace")
    for relative in payload["expected_artifacts"]:
        _safe_relative(relative)
    environment = payload["environment"]
    names = tuple(name.casefold() for name, _ in environment)
    if len(names) != len(set(names)):
        raise ValueError("remote environment names must be unique")


def _worker_environment(payload_path: Path) -> dict[str, str]:
    payload = _read_json(payload_path)
    environment = dict(payload["environment"])
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


def _extract_safe_archive(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, mode="r:*") as stream:
        seen: set[str] = set()
        for member in stream.getmembers():
            relative = _safe_relative(member.name)
            normalized = str(PurePosixPath(*relative.parts))
            if normalized in seen:
                raise ValueError("staging archive contains duplicate paths")
            seen.add(normalized)
            if member.issym() or member.islnk() or not (
                member.isfile() or member.isdir()
            ):
                raise ValueError("staging archive contains an unsupported member")
            target = (destination / relative).resolve(strict=False)
            target.relative_to(destination.resolve(strict=True))
        for member in stream.getmembers():
            stream.extract(member, destination)


def _reconciled_phase(
    event: dict[str, Any] | None,
    *,
    process_matches: bool,
    missing: tuple[str, ...],
    heartbeat: dict[str, Any] | None,
    stale_after: float,
) -> tuple[str, str | None]:
    if event is None:
        return "RUNNING_UNKNOWN", "no durable remote status event"
    phase = str(event["phase"])
    if phase == "COMPLETED" and missing:
        return "FAILED", "completed remote process is missing required artifacts"
    if phase in TERMINAL_PHASES:
        return phase, event.get("detail")
    if not process_matches:
        return "RUNNING_UNKNOWN", "recorded remote process identity is not live"
    signal_at = heartbeat["observed_at"] if heartbeat else event["observed_at"]
    age = (datetime.now(UTC) - datetime.fromisoformat(signal_at)).total_seconds()
    if age > stale_after:
        return "RUNNING_UNKNOWN", "remote heartbeat is stale"
    if phase == "PREPARED":
        return "RUNNING", "remote launcher is live; target startup is pending"
    return phase, event.get("detail")


def _produced_artifacts(payload: dict[str, Any]) -> tuple[str, ...]:
    output_root = Path(payload["output_root"])
    return tuple(
        relative
        for relative in payload["expected_artifacts"]
        if (output_root / _safe_relative(relative)).is_file()
    )


def _source_entries(
    output_root: Path,
    required: tuple[str, ...],
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    entries: list[dict[str, Any]] = []
    missing: list[str] = []
    for name in required:
        relative = _safe_relative(name)
        path = (output_root / relative).resolve(strict=False)
        path.relative_to(output_root)
        if not path.is_file():
            missing.append(name)
            continue
        entries.append(
            {
                "relative_path": name,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return entries, tuple(missing)


def _process_identity(pid: int) -> dict[str, Any]:
    return {
        "pid": pid,
        "start_ticks": _process_start_ticks(pid),
        "recorded_at": _now(),
    }


def _process_start_ticks(pid: int) -> int:
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    fields_after_name = stat[stat.rfind(")") + 2 :].split()
    return int(fields_after_name[19])


def _identity_is_live(identity: dict[str, Any] | None) -> bool:
    if identity is None:
        return False
    try:
        pid = int(identity["pid"])
        os.kill(pid, 0)
        return _process_start_ticks(pid) == int(identity["start_ticks"])
    except (KeyError, OSError, ValueError):
        return False


def _terminate_exact_tree(
    identity: dict[str, Any],
    *,
    timeout_seconds: float,
) -> None:
    if not _identity_is_live(identity):
        return
    root_pid = int(identity["pid"])
    targets = _descendant_identities(root_pid) + (identity,)
    for target in targets:
        _signal_exact(target, signal.SIGTERM)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not any(_identity_is_live(target) for target in targets):
            return
        time.sleep(0.1)
    for target in targets:
        _signal_exact(target, signal.SIGKILL)


def _descendant_identities(pid: int) -> tuple[dict[str, Any], ...]:
    children_path = Path(f"/proc/{pid}/task/{pid}/children")
    try:
        child_pids = tuple(
            int(value)
            for value in children_path.read_text(encoding="utf-8").split()
        )
    except (OSError, ValueError):
        return ()
    descendants: list[dict[str, Any]] = []
    for child_pid in child_pids:
        try:
            child_identity = _process_identity(child_pid)
        except OSError:
            continue
        descendants.extend(_descendant_identities(child_pid))
        descendants.append(child_identity)
    return tuple(descendants)


def _signal_exact(identity: dict[str, Any], signal_number: int) -> None:
    if not _identity_is_live(identity):
        return
    try:
        os.kill(int(identity["pid"]), signal_number)
    except OSError:
        pass


def _read_identity(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload.get("pid"), int):
        raise ValueError("remote process identity is missing pid")
    if not isinstance(payload.get("start_ticks"), int):
        raise ValueError("remote process identity is missing start_ticks")
    return payload


def _read_identity_optional(path: Path) -> dict[str, Any] | None:
    return _read_identity(path) if path.is_file() else None


def _latest_json(root: Path) -> dict[str, Any] | None:
    candidates = tuple(sorted(root.glob("*.json")))
    return _read_json(candidates[-1]) if candidates else None


def _status_event(
    phase: str,
    *,
    process_id: int | None = None,
    exit_code: int | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "observed_at": _now(),
        "process_id": process_id,
        "exit_code": exit_code,
        "detail": detail,
    }


def _write_event(root: Path, label: str, payload: dict[str, Any]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{time.time_ns():020d}-{label}-{uuid.uuid4().hex}.json"
    _write_json_exclusive(path, payload)
    return path


def _write_or_verify(path: Path, payload: dict[str, Any]) -> None:
    encoded = _canonical_json(payload)
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError("governed remote manifest differs")
        return
    try:
        _write_json_exclusive(path, payload)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError("governed remote manifest differs") from None


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(_canonical_json(payload))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("remote JSON payload must be an object")
    return payload


def _canonical_json(payload: dict[str, Any]) -> str:
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        raise ValueError("remote artifact path must be safe and relative")
    return path


def _confined(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=False)
    resolved.relative_to(root.resolve(strict=True))
    return resolved


def _size_or_zero(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _required_path(value: str | None) -> Path:
    if not value:
        raise ValueError("required path argument is missing")
    return Path(value)


def _now() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())

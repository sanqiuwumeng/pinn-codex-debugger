"""Durable local worker used by LocalProcessRunnerBackend."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    parser.add_argument("--run-root", required=True)
    arguments = parser.parse_args()
    payload_path = Path(arguments.payload).resolve(strict=True)
    run_root = Path(arguments.run_root).resolve(strict=True)
    if payload_path.parent != run_root:
        raise ValueError("worker payload must be inside the declared run root")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    status_root = run_root / "status-events"
    heartbeat_root = run_root / "heartbeats"
    stdout_path = run_root / "stdout.log"
    stderr_path = run_root / "stderr.log"
    _write_event(status_root, "starting", _status("PREPARED"))
    try:
        with stdout_path.open("xb") as stdout_stream, stderr_path.open(
            "xb"
        ) as stderr_stream:
            process = subprocess.Popen(
                tuple(payload["command"]),
                cwd=payload["working_directory"],
                stdout=stdout_stream,
                stderr=stderr_stream,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                ),
                start_new_session=os.name != "nt",
            )
            identity = {
                "pid": process.pid,
                "create_time": psutil.Process(process.pid).create_time(),
                "recorded_at": _now(),
            }
            _write_json_exclusive(run_root / "process-identity.json", identity)
            _write_event(
                status_root,
                "running",
                _status("RUNNING", process_id=process.pid),
            )
            interval = float(payload["heartbeat_interval_seconds"])
            while process.poll() is None:
                _write_event(
                    heartbeat_root,
                    "heartbeat",
                    {
                        "observed_at": _now(),
                        "process_id": process.pid,
                    },
                )
                time.sleep(interval)
            exit_code = int(process.wait())
        cancellation_recorded = (
            run_root / "cancellation-approval.json"
        ).is_file()
        if cancellation_recorded:
            phase = "CANCELLED"
        else:
            phase = "COMPLETED" if exit_code == 0 else "FAILED"
        _write_event(
            status_root,
            phase.casefold(),
            _status(phase, process_id=process.pid, exit_code=exit_code),
        )
        return exit_code
    except BaseException as error:
        _write_event(
            status_root,
            "worker-failed",
            _status(
                "FAILED",
                detail=f"{type(error).__name__}: {error}",
            ),
        )
        raise


def _status(
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


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _now() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the portable, non-training release gates with one explicit interpreter."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any


def _run(label: str, command: tuple[str, ...], cwd: Path, environment: dict[str, str]) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    combined = completed.stdout + "\n" + completed.stderr
    counts = tuple(int(value) for value in re.findall(r"Ran (\d+) tests?", combined))
    return {
        "label": label,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "exit_code": completed.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "test_count": sum(counts),
        "stdout_lines": len(completed.stdout.splitlines()),
        "stderr_lines": len(completed.stderr.splitlines()),
    }


def run(repo_root: Path, python: Path) -> dict[str, Any]:
    root = repo_root.resolve(strict=True)
    interpreter = python.resolve(strict=True)
    if not interpreter.is_file():
        raise ValueError("orchestration interpreter must be an existing file")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    py = str(interpreter)
    commands = (
        (
            "orchestrator-tests",
            (py, "-m", "unittest", "discover", "-s", "tests", "-v"),
            root / "orchestrator",
        ),
        (
            "mcp-tests",
            (py, "-m", "unittest", "discover", "-s", ".", "-t", ".", "-p", "test*.py", "-v"),
            root / "mcp-server",
        ),
        (
            "retrieval-benchmark-contract-tests",
            (py, "-m", "unittest", "discover", "-s", ".", "-t", ".", "-p", "test*.py", "-v"),
            root / "qualification" / "qwen",
        ),
        (
            "qualification-contract-tests",
            (
                py,
                "-m",
                "unittest",
                "qualification.poisson.test_aggregate_poisson_multiseed",
                "qualification.poisson.test_qualification_contracts",
                "-v",
            ),
            root,
        ),
        ("dependency-consistency", (py, "-m", "pip", "check"), root),
        (
            "repository-security-and-release-layout",
            (
                py,
                str(root / "skills" / "pinn-rag-strategy-system" / "scripts" / "audit_repository.py"),
                "--repo-root",
                str(root),
            ),
            root,
        ),
    )
    results = [_run(label, command, cwd, environment) for label, command, cwd in commands]
    return {
        "schema_version": "1.0",
        "status": "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL",
        "repository_root": str(root),
        "python": str(interpreter),
        "total_tests": sum(int(item["test_count"]) for item in results),
        "gates": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    try:
        report = run(arguments.repo_root, arguments.python)
        if arguments.report is not None:
            destination = arguments.report.resolve(strict=False)
            if destination.exists() or not destination.parent.is_dir():
                raise FileExistsError("report destination must be new with an existing parent")
            destination.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as error:
        report = {
            "schema_version": "1.0",
            "status": "ERROR",
            "error_type": type(error).__name__,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

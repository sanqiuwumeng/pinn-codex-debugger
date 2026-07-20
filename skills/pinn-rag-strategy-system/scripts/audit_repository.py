#!/usr/bin/env python3
"""Read-only security and portability audit for the PINN strategy repository."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any


REQUIRED_PATHS = (
    "orchestrator/pyproject.toml",
    "mcp-server/pyproject.toml",
    "retrieval-runtime/qwen3_jsonl_gateway.py",
    "validation/remote_e2e/run_remote_full_chain.py",
    "openspec",
)

CONTENT_RULES = (
    (
        "private-key",
        re.compile(rb"-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----"),
    ),
    (
        "direct-ssh-connection",
        re.compile(rb"\bssh\s+-p\s+\d+\s+[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+"),
    ),
    (
        "assigned-credential",
        re.compile(
            rb"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token|secret)\b"
            rb"\s*[:=]\s*['\"][^'\"\r\n]{4,}['\"]"
        ),
    ),
)


def _run_git(root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(root), *arguments),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("repository audit requires a readable Git worktree")
    return completed.stdout


def _tracked_files(root: Path) -> tuple[tuple[str, Path], ...]:
    raw = _run_git(root, "ls-files", "-z")
    names = tuple(item.decode("utf-8") for item in raw.split(b"\0") if item)
    files: list[tuple[str, Path]] = []
    for name in names:
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or "\\" in name:
            raise ValueError("Git contains a non-portable tracked path")
        candidate = root / Path(*pure.parts)
        if candidate.is_symlink():
            files.append((name, candidate))
            continue
        path = candidate.resolve(strict=True)
        path.relative_to(root)
        files.append((name, path))
    return tuple(files)


def _content_findings(files: tuple[tuple[str, Path], ...]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, path in files:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
            continue
        content = path.read_bytes()
        for rule, pattern in CONTENT_RULES:
            if pattern.search(content):
                findings.append({"rule": rule, "path": name})
    return findings


def _call_name(node: ast.Call) -> str:
    parts: list[str] = []
    value: ast.AST = node.func
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def _ast_findings(files: tuple[tuple[str, Path], ...]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, path in files:
        if path.is_symlink() or path.suffix != ".py" or not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
        except (SyntaxError, UnicodeDecodeError) as error:
            findings.append(
                {"rule": "unparseable-python", "path": name, "line": error.lineno}
            )
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = _call_name(node)
            rule: str | None = None
            is_builtin_dynamic_call = (
                isinstance(node.func, ast.Name)
                and node.func.id in {"eval", "exec", "compile"}
            )
            if is_builtin_dynamic_call or called == "os.system":
                rule = "dynamic-command-execution"
            elif called in {
                "pickle.load",
                "pickle.loads",
                "marshal.load",
                "marshal.loads",
                "yaml.load",
            }:
                rule = "unsafe-deserialization"
            elif called.endswith(".load") and any(
                keyword.arg == "allow_pickle"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            ):
                rule = "pickle-enabled-array-load"
            elif called in {"subprocess.run", "subprocess.Popen"} and any(
                keyword.arg == "shell"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            ):
                rule = "shell-enabled-subprocess"
            if rule is not None:
                findings.append({"rule": rule, "path": name, "line": node.lineno})
    return findings


def _dependency_findings(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for relative in ("orchestrator/pyproject.toml", "mcp-server/pyproject.toml"):
        path = root / relative
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
        dependencies = payload.get("project", {}).get("dependencies", ())
        for dependency in dependencies:
            if "==" not in dependency:
                findings.append(
                    {"rule": "unpinned-runtime-dependency", "path": relative, "value": dependency}
                )
    return findings


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repository root must be a directory")
    missing = tuple(item for item in REQUIRED_PATHS if not (root / item).exists())
    files = _tracked_files(root)
    symlinks = tuple(name for name, path in files if path.is_symlink())
    findings = _content_findings(files) + _ast_findings(files) + _dependency_findings(root)
    findings.extend({"rule": "tracked-symlink", "path": name} for name in symlinks)
    findings.extend({"rule": "missing-required-path", "path": item} for item in missing)
    return {
        "schema_version": "1.0",
        "status": "PASS" if not findings else "FAIL",
        "repository_root": str(root),
        "tracked_file_count": len(files),
        "checks": {
            "required_layout": not missing,
            "tracked_paths_portable": True,
            "tracked_symlinks_absent": not symlinks,
            "credential_markers_absent": not any(
                item["rule"] in {"private-key", "direct-ssh-connection", "assigned-credential"}
                for item in findings
            ),
            "dangerous_python_calls_absent": not any(
                item["rule"]
                in {
                    "dynamic-command-execution",
                    "unsafe-deserialization",
                    "pickle-enabled-array-load",
                    "shell-enabled-subprocess",
                    "unparseable-python",
                }
                for item in findings
            ),
            "runtime_dependencies_exactly_pinned": not any(
                item["rule"] == "unpinned-runtime-dependency" for item in findings
            ),
        },
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    arguments = parser.parse_args()
    try:
        report = audit(arguments.repo_root)
    except (OSError, RuntimeError, ValueError) as error:
        report = {
            "schema_version": "1.0",
            "status": "ERROR",
            "error_type": type(error).__name__,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2 if arguments.pretty else None, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify a transferred Wiki-RAG-PINN completion bundle without trusting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


CREDENTIAL_PATTERNS = (
    re.compile(r"-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----"),
    re.compile(r"\bssh\s+-p\s+\d+\s+[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+"),
    re.compile(
        r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token|secret)\b"
        r"\s*[:=]\s*['\"][^'\"\r\n]{4,}['\"]"
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: str) -> Path:
    pure = PurePosixPath(value)
    if (
        not value
        or pure.is_absolute()
        or ".." in pure.parts
        or "\\" in value
        or pure == PurePosixPath(".")
    ):
        raise ValueError("completion manifest contains an unsafe relative path")
    return Path(*pure.parts)


def _require_hash(value: str, length: int, label: str) -> None:
    if re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError(f"{label} is not a lowercase hexadecimal hash")


def verify(
    root: Path,
    expected_commit: str | None,
    expected_source_sha256: str | None,
) -> dict[str, Any]:
    result_root = root.resolve(strict=True)
    if not result_root.is_dir():
        raise ValueError("result root must be a directory")
    manifest_path = result_root / "completion-manifest.json"
    marker_path = result_root / "FULL_CHAIN_PASS"
    if not manifest_path.is_file() or not marker_path.is_file():
        raise ValueError("completion manifest or terminal marker is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("status") != "PASS":
        raise ValueError("completion manifest is not a PASS object")
    commit = manifest.get("repo_commit")
    source_sha = manifest.get("source_archive_sha256")
    if not isinstance(commit, str) or not isinstance(source_sha, str):
        raise ValueError("completion manifest lacks source identity")
    _require_hash(commit, 40, "repository commit")
    _require_hash(source_sha, 64, "source archive SHA-256")
    if expected_commit is not None and commit != expected_commit:
        raise ValueError("repository commit differs from the expected commit")
    if expected_source_sha256 is not None and source_sha != expected_source_sha256:
        raise ValueError("source archive hash differs from the expected hash")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("completion manifest has no file inventory")
    expected_names: set[str] = set()
    total_bytes = 0
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("completion file inventory entry is not an object")
        relative_value = item.get("relative_path")
        sha = item.get("sha256")
        size = item.get("size_bytes")
        if not isinstance(relative_value, str) or not isinstance(sha, str) or not isinstance(size, int):
            raise ValueError("completion file inventory entry is incomplete")
        _require_hash(sha, 64, "file SHA-256")
        relative = _safe_relative(relative_value)
        normalized = PurePosixPath(*relative.parts).as_posix()
        if normalized in expected_names:
            raise ValueError("completion file inventory contains a duplicate path")
        expected_names.add(normalized)
        path = (result_root / relative).resolve(strict=True)
        path.relative_to(result_root)
        if not path.is_file() or path.stat().st_size != size or _sha256(path) != sha:
            raise ValueError("completion file failed size or hash verification")
        total_bytes += size

    observed_names = {
        path.relative_to(result_root).as_posix()
        for path in result_root.rglob("*")
        if path.is_file() and path.name not in {"completion-manifest.json", "FULL_CHAIN_PASS"}
    }
    if observed_names != expected_names:
        raise ValueError("transferred result file set differs from the manifest")
    if manifest.get("file_count_before_completion_manifest") != len(files):
        raise ValueError("completion file count is inconsistent")
    if manifest.get("total_bytes_before_completion_manifest") != total_bytes:
        raise ValueError("completion byte total is inconsistent")

    completion_sha = _sha256(manifest_path)
    if marker_path.read_text(encoding="utf-8") != f"completion_manifest_sha256={completion_sha}\n":
        raise ValueError("terminal marker does not authenticate the completion manifest")
    wiki = manifest.get("wiki")
    retrieval = manifest.get("retrieval")
    if not isinstance(wiki, dict) or wiki.get("publication_code") not in {
        "WIKI_PUBLISHED",
        "WIKI_VERIFIED",
    }:
        raise ValueError("formal Wiki publication gate is absent")
    if (
        not isinstance(retrieval, dict)
        or retrieval.get("published_wiki_retrieved") is not True
        or retrieval.get("conflict_visible") is not True
        or not retrieval.get("embedding_model_id")
        or not retrieval.get("reranker_model_id")
    ):
        raise ValueError("RAG provenance or conflict-visibility gate is absent")
    if manifest.get("credential_scan") != "PASS":
        raise ValueError("remote credential scan did not pass")
    for path in result_root.rglob("*"):
        if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in CREDENTIAL_PATTERNS):
            raise ValueError("credential marker detected in transferred evidence")
    return {
        "schema_version": "1.0",
        "status": "PASS",
        "result_root": str(result_root),
        "repo_commit": commit,
        "source_archive_sha256": source_sha,
        "completion_manifest_sha256": completion_sha,
        "verified_file_count": len(files),
        "verified_total_bytes": total_bytes,
        "wiki_id": wiki.get("chunk_id"),
        "embedding_model_id": retrieval.get("embedding_model_id"),
        "reranker_model_id": retrieval.get("reranker_model_id"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--expected-commit")
    parser.add_argument("--expected-source-sha256")
    arguments = parser.parse_args()
    try:
        if arguments.expected_commit is not None:
            _require_hash(arguments.expected_commit, 40, "expected commit")
        if arguments.expected_source_sha256 is not None:
            _require_hash(arguments.expected_source_sha256, 64, "expected source SHA-256")
        report = verify(
            arguments.result_root,
            arguments.expected_commit,
            arguments.expected_source_sha256,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        report = {
            "schema_version": "1.0",
            "status": "FAIL",
            "error_type": type(error).__name__,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

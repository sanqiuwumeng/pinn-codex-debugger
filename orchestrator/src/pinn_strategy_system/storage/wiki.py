"""Append-only atomic persistence for formally published Wiki entries."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from pinn_strategy_system.contracts import (
    ArtifactRef,
    ChunkMetadata,
    KnowledgeChunk,
    PublishedWikiEntry,
    SourceRef,
    WikiEntryCandidate,
    WikiPublicationReceipt,
)


class WikiPublicationConflictError(RuntimeError):
    pass


class PublishedWikiStore:
    def __init__(self, root: str | Path) -> None:
        path = Path(root)
        if not path.is_absolute():
            raise ValueError("knowledge root must be absolute")
        if not path.exists() or not path.is_dir():
            raise ValueError("knowledge root must be an existing directory")
        self._root = path.resolve(strict=True)

    def publish(self, entry: PublishedWikiEntry) -> WikiPublicationReceipt:
        _verify_candidate_evidence(entry.candidate)
        wiki_id = _safe_segment(entry.publication.wiki_id, "wiki_id")
        version = entry.candidate.version
        version_name = f"v{version:04d}"
        target = self._root / "wiki" / wiki_id / version_name
        expected = _publication_files(entry=entry, target=target)
        if target.exists():
            _verify_existing(target=target, expected=expected)
            return _receipt(
                entry=entry,
                target=target,
                expected=expected,
                idempotent_replay=True,
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        staging_root = self._root / ".wiki-staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                prefix=f"{wiki_id}-{version_name}-",
                dir=staging_root,
            )
        )
        for name, content in expected.items():
            _write_new(staging / name, content)
        try:
            os.rename(staging, target)
        except OSError as error:
            if target.exists():
                _verify_existing(target=target, expected=expected)
                return _receipt(
                    entry=entry,
                    target=target,
                    expected=expected,
                    idempotent_replay=True,
                )
            raise WikiPublicationConflictError(
                "Wiki version could not be committed atomically"
            ) from error
        return _receipt(
            entry=entry,
            target=target,
            expected=expected,
            idempotent_replay=False,
        )


def _publication_files(
    *,
    entry: PublishedWikiEntry,
    target: Path,
) -> dict[str, bytes]:
    publication = _canonical_json(entry.model_dump(mode="json"))
    markdown = _render_markdown(entry).encode("utf-8")
    markdown_sha = hashlib.sha256(markdown).hexdigest()
    markdown_lines = markdown.decode("utf-8").splitlines()
    indexed_text = "\n".join(
        (
            entry.candidate.title,
            entry.candidate.conclusion,
        )
    )
    chunk = KnowledgeChunk(
        chunk_id=f"{entry.publication.wiki_id}-v{entry.candidate.version:04d}",
        text=indexed_text,
        chunk_sha256=hashlib.sha256(indexed_text.encode("utf-8")).hexdigest(),
        metadata=ChunkMetadata(
            project_id=entry.publication.project_id,
            source_ref=SourceRef(
                uri=(target / "entry.md").as_uri(),
                sha256=markdown_sha,
                line_start=1,
                line_end=len(markdown_lines),
            ),
            repo_commit=entry.publication.repo_commit,
            experiment_id=entry.candidate.run_id,
            run_id=entry.candidate.run_id,
            model_family=entry.publication.model_family,
            pde_family=entry.publication.pde_family,
            task_type=entry.publication.task_type,
            domain_provider_id=entry.publication.domain_provider_id,
            output_channels=entry.publication.output_channels,
            dimensional_signatures=entry.publication.dimensional_signatures,
            failure_signatures=entry.publication.failure_signatures,
            framework=entry.publication.framework,
            document_type="WIKI",
            validation_status="APPROVED",
            valid_from=entry.publication.published_at,
            supersedes=entry.candidate.supersedes,
            language=entry.publication.language,
        ),
    )
    document = {
        "schema_version": "1.0",
        "chunk": chunk.model_dump(mode="json"),
        "applicable_versions": (
            [entry.publication.repo_commit]
            if entry.publication.repo_commit is not None
            else []
        ),
        "claims": [
            {"schema_version": "1.0", "key": key, "value": value}
            for key, value in sorted(entry.publication.claims.items())
        ],
    }
    index = _canonical_json(document)
    payloads = {
        "publication.json": publication,
        "entry.md": markdown,
        "entry.index.json": index,
    }
    manifest_payload = {
        "schema_version": "1.0",
        "wiki_id": entry.publication.wiki_id,
        "version": entry.candidate.version,
        "files": {
            name: {
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for name, content in sorted(payloads.items())
        },
    }
    payloads["manifest.json"] = _canonical_json(manifest_payload)
    return payloads


def _render_markdown(entry: PublishedWikiEntry) -> str:
    candidate = entry.candidate
    evidence = _candidate_artifacts(candidate)
    lines = [
        f"# {candidate.title}",
        "",
        f"- Wiki ID: `{entry.publication.wiki_id}`",
        f"- Version: `{candidate.version}`",
        "- Validity: `VALID`",
        f"- Evidence level: `{candidate.evidence_level.value}`",
        f"- Claim scope: `{candidate.claim_scope.value}`",
        f"- Run ID: `{candidate.run_id}`",
        f"- Published at: `{entry.publication.published_at.isoformat()}`",
        f"- Approval ID: `{entry.approval.approval_id}`",
        "",
        "## Conclusion",
        "",
        candidate.conclusion,
        "",
        "## Evidence anchors",
        "",
    ]
    lines.extend(
        f"- `{artifact.artifact_id}`: `{artifact.sha256}`"
        for artifact in evidence
    )
    if candidate.supersedes:
        lines.extend(
            (
                "",
                "## Supersedes",
                "",
                *(f"- `{item}`" for item in candidate.supersedes),
            )
        )
    return "\n".join(lines) + "\n"


def _candidate_artifacts(candidate: WikiEntryCandidate) -> tuple[ArtifactRef, ...]:
    return (
        candidate.source_snapshot_ref,
        *candidate.dataset_refs,
        candidate.environment_ref,
        candidate.metric_report_ref,
        candidate.physical_audit_ref,
        candidate.reproducibility_report_ref,
        candidate.validation_report_ref,
    )


def _verify_candidate_evidence(candidate: WikiEntryCandidate) -> None:
    for artifact in _candidate_artifacts(candidate):
        parsed = urlparse(artifact.uri)
        if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
            raise ValueError("formal Wiki evidence must use local file URIs")
        path = Path(url2pathname(parsed.path)).resolve(strict=True)
        if not path.is_file():
            raise ValueError("formal Wiki evidence must reference files")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != artifact.sha256:
            raise ValueError("formal Wiki evidence hash mismatch")
        if artifact.size_bytes is not None and len(content) != artifact.size_bytes:
            raise ValueError("formal Wiki evidence size mismatch")


def _verify_existing(*, target: Path, expected: dict[str, bytes]) -> None:
    if not target.is_dir():
        raise WikiPublicationConflictError("Wiki version target is not a directory")
    observed_names = {path.name for path in target.iterdir() if path.is_file()}
    if observed_names != set(expected):
        raise WikiPublicationConflictError("Wiki version file set conflicts")
    for name, content in expected.items():
        if (target / name).read_bytes() != content:
            raise WikiPublicationConflictError("Wiki version content conflicts")


def _receipt(
    *,
    entry: PublishedWikiEntry,
    target: Path,
    expected: dict[str, bytes],
    idempotent_replay: bool,
) -> WikiPublicationReceipt:
    return WikiPublicationReceipt(
        wiki_id=entry.publication.wiki_id,
        version=entry.candidate.version,
        directory_uri=target.as_uri(),
        publication_ref=_file_ref(entry, target, expected, "publication.json"),
        markdown_ref=_file_ref(entry, target, expected, "entry.md"),
        index_ref=_file_ref(entry, target, expected, "entry.index.json"),
        manifest_ref=_file_ref(entry, target, expected, "manifest.json"),
        idempotent_replay=idempotent_replay,
    )


def _file_ref(
    entry: PublishedWikiEntry,
    target: Path,
    expected: dict[str, bytes],
    name: str,
) -> ArtifactRef:
    content = expected[name]
    suffix = name.replace(".", "-")
    return ArtifactRef(
        artifact_id=(
            f"{entry.publication.wiki_id}-v{entry.candidate.version:04d}-{suffix}"
        ),
        uri=(target / name).as_uri(),
        sha256=hashlib.sha256(content).hexdigest(),
        media_type=(
            "text/markdown" if name.endswith(".md") else "application/json"
        ),
        size_bytes=len(content),
    )


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_new(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _safe_segment(value: str, label: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", value) is None:
        raise ValueError(f"{label} must be one safe path segment")
    return value

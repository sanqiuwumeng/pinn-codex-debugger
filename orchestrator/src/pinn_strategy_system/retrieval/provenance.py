"""Deterministic provenance checks performed before vector indexing."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import unquote, urlparse

from .models import IndexedKnowledgeDocument


class ProvenanceError(ValueError):
    pass


class ProvenanceValidator:
    def validate(
        self,
        document: IndexedKnowledgeDocument,
    ) -> tuple[str, ...]:
        chunk = document.chunk
        metadata = chunk.metadata
        source = metadata.source_ref
        issues: list[str] = []

        actual_chunk_hash = hashlib.sha256(
            chunk.text.encode("utf-8")
        ).hexdigest()
        if actual_chunk_hash != chunk.chunk_sha256:
            issues.append("chunk_sha256 does not match chunk text")
        if not metadata.repo_commit:
            issues.append("repo_commit is required for rebuildable provenance")
        if source.line_start is None and metadata.artifact_range is None:
            issues.append("source range or artifact_range is required")

        parsed = urlparse(source.uri)
        if parsed.scheme == "file":
            issues.extend(_validate_file_source(parsed, source.sha256, metadata))
        elif parsed.scheme not in {"artifact", "wiki", "skill"}:
            issues.append(f"unsupported authoritative source scheme: {parsed.scheme}")
        return tuple(issues)

    def require(self, document: IndexedKnowledgeDocument) -> None:
        issues = self.validate(document)
        if issues:
            joined = "; ".join(issues)
            raise ProvenanceError(
                f"invalid provenance for {document.chunk.chunk_id}: {joined}"
            )


def _validate_file_source(parsed, expected_sha256, metadata) -> tuple[str, ...]:
    if parsed.netloc not in {"", "localhost"}:
        return ("file source must be local for deterministic validation",)
    decoded = unquote(parsed.path)
    if len(decoded) >= 3 and decoded[0] == "/" and decoded[2] == ":":
        decoded = decoded[1:]
    path = Path(decoded)
    if not path.exists() or not path.is_file():
        return ("file source does not exist",)
    content = path.read_bytes()
    issues: list[str] = []
    actual_sha = hashlib.sha256(content).hexdigest()
    if actual_sha != expected_sha256:
        issues.append("source sha256 does not match authoritative file")
    line_end = metadata.source_ref.line_end
    if line_end is not None:
        line_count = len(content.decode("utf-8").splitlines())
        if line_end > line_count:
            issues.append("source line range exceeds authoritative file")
    return tuple(issues)

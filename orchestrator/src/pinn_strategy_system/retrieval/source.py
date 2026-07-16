"""Read-only loader for Git-managed index documents."""

from __future__ import annotations

from pathlib import Path

from .models import IndexedKnowledgeDocument


class FilesystemKnowledgeSource:
    def __init__(self, root: str | Path) -> None:
        path = Path(root)
        if not path.is_absolute():
            raise ValueError("knowledge source root must be absolute")
        if not path.exists() or not path.is_dir():
            raise ValueError("knowledge source root must be an existing directory")
        self._root = path.resolve(strict=False)

    @property
    def root(self) -> Path:
        return self._root

    def load_documents(self) -> tuple[IndexedKnowledgeDocument, ...]:
        documents = tuple(
            IndexedKnowledgeDocument.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            for path in sorted(self._root.rglob("*.index.json"))
        )
        chunk_ids = tuple(document.chunk.chunk_id for document in documents)
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("knowledge source contains duplicate chunk_id values")
        return documents

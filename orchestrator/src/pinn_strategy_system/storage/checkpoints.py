"""Explicit factory for the LangGraph-owned checkpoint database."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


class SQLiteCheckpointStore:
    def __init__(self, database_path: str | Path) -> None:
        path = Path(database_path)
        if not path.is_absolute():
            raise ValueError("checkpoint database path must be absolute")
        if not path.parent.exists():
            raise ValueError(
                "checkpoint database parent directory must already exist"
            )
        self._database_path = path.resolve(strict=False)

    @property
    def database_path(self) -> Path:
        return self._database_path

    @contextmanager
    def open(self):
        with SqliteSaver.from_conn_string(
            str(self._database_path)
        ) as checkpointer:
            yield checkpointer

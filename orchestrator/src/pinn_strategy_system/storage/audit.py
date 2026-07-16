"""Append-only SQLite audit events with caller-supplied timestamps."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from pinn_strategy_system.contracts import VersionedModel


class AuditRecord(VersionedModel):
    record_id: str
    subject_id: str
    category: str
    occurred_at: datetime
    payload: dict[str, JsonValue]


class AppendOnlyAuditStore:
    def __init__(self, database_path: str | Path) -> None:
        path = Path(database_path)
        if not path.is_absolute():
            raise ValueError("audit database path must be absolute")
        if not path.parent.exists():
            raise ValueError("audit database parent directory must already exist")
        self._database_path = path.resolve(strict=False)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL UNIQUE,
                    subject_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def append(
        self,
        *,
        record_id: str,
        subject_id: str,
        category: str,
        occurred_at: datetime,
        payload: VersionedModel,
    ) -> AuditRecord:
        if occurred_at.tzinfo is None:
            raise ValueError("audit timestamps must be timezone-aware")
        record = AuditRecord(
            record_id=record_id,
            subject_id=subject_id,
            category=category,
            occurred_at=occurred_at,
            payload=payload.model_dump(mode="json"),
        )
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO audit_events (
                        record_id,
                        subject_id,
                        category,
                        occurred_at,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record.record_id,
                        record.subject_id,
                        record.category,
                        record.occurred_at.isoformat(),
                        json.dumps(
                            record.payload,
                            ensure_ascii=False,
                            allow_nan=False,
                            sort_keys=True,
                        ),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError(f"duplicate audit record_id: {record_id}") from error
        return record

    def records_for(self, subject_id: str) -> tuple[AuditRecord, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT record_id, subject_id, category, occurred_at, payload_json
                FROM audit_events
                WHERE subject_id = ?
                ORDER BY sequence
                """,
                (subject_id,),
            ).fetchall()
        return tuple(
            AuditRecord(
                record_id=row[0],
                subject_id=row[1],
                category=row[2],
                occurred_at=datetime.fromisoformat(row[3]),
                payload=json.loads(row[4]),
            )
            for row in rows
        )

    @contextmanager
    def _connection(self):
        with closing(sqlite3.connect(self._database_path)) as connection:
            with connection:
                yield connection

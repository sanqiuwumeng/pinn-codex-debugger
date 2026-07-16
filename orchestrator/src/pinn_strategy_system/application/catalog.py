"""Durable workflow-to-case catalog with append-only case revisions."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from .contracts import ApplicationResult, OperatorCase


class SQLiteWorkflowCatalog:
    def __init__(self, database_path: Path) -> None:
        if not database_path.is_absolute():
            raise ValueError("workflow catalog path must be absolute")
        if not database_path.parent.is_dir():
            raise ValueError("workflow catalog parent must exist")
        self._database_path = database_path.resolve(strict=False)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS operator_workflows_v1 (
                    workflow_id TEXT PRIMARY KEY,
                    case_path TEXT NOT NULL,
                    case_sha256 TEXT NOT NULL,
                    case_json TEXT NOT NULL,
                    last_result_json TEXT
                );
                CREATE TABLE IF NOT EXISTS operator_case_revisions_v1 (
                    revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    case_path TEXT NOT NULL,
                    case_sha256 TEXT NOT NULL,
                    case_json TEXT NOT NULL
                );
                """
            )

    def register(self, case: OperatorCase, case_path: Path) -> None:
        if not case_path.is_absolute() or not case_path.is_file():
            raise ValueError("operator case path must be an existing absolute file")
        encoded = case.model_dump_json()
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        workflow_id = case.request.workflow_id
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT case_path, case_sha256, case_json
                FROM operator_workflows_v1 WHERE workflow_id = ?
                """,
                (workflow_id,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO operator_workflows_v1 (
                        workflow_id, case_path, case_sha256, case_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (workflow_id, str(case_path), digest, encoded),
                )
                return
            if row[1] == digest:
                return
            connection.execute(
                """
                INSERT INTO operator_case_revisions_v1 (
                    workflow_id, case_path, case_sha256, case_json
                ) VALUES (?, ?, ?, ?)
                """,
                (workflow_id, row[0], row[1], row[2]),
            )
            connection.execute(
                """
                UPDATE operator_workflows_v1
                SET case_path = ?, case_sha256 = ?, case_json = ?
                WHERE workflow_id = ?
                """,
                (str(case_path), digest, encoded, workflow_id),
            )

    def load(self, workflow_id: str) -> OperatorCase:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT case_json FROM operator_workflows_v1 WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        if row is None:
            raise KeyError("workflow is not registered")
        return OperatorCase.model_validate_json(row[0])

    def record_result(self, result: ApplicationResult) -> None:
        if result.workflow_id is None:
            return
        with self._connection() as connection:
            updated = connection.execute(
                """
                UPDATE operator_workflows_v1 SET last_result_json = ?
                WHERE workflow_id = ?
                """,
                (result.model_dump_json(), result.workflow_id),
            ).rowcount
        if updated != 1:
            raise KeyError("workflow is not registered")

    @contextmanager
    def _connection(self):
        with closing(sqlite3.connect(self._database_path)) as connection:
            with connection:
                yield connection

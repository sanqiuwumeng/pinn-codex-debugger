"""Manifest-first, idempotent runner boundary with no implicit backend."""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pinn_strategy_system.contracts import (
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    RunManifest,
    RunSubmission,
    RunSubmissionStatus,
)


class RunnerBackend(Protocol):
    def launch(self, manifest: RunManifest) -> str: ...


class IdempotencyConflictError(RuntimeError):
    pass


class RunLaunchUncertainError(RuntimeError):
    def __init__(self, run_id: str) -> None:
        super().__init__(
            f"launch outcome is uncertain for {run_id}; reconcile before retry"
        )
        self.run_id = run_id


@dataclass(frozen=True)
class _Reservation:
    submission: RunSubmission
    created: bool


class SQLiteRunRegistry:
    """Own only run-launch metadata; artifacts remain in their declared store."""

    def __init__(self, database_path: str | Path) -> None:
        path = Path(database_path)
        if not path.is_absolute():
            raise ValueError("run registry path must be absolute")
        if not path.parent.exists():
            raise ValueError("run registry parent directory must already exist")
        self._path = str(path)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_launches (
                    idempotency_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL UNIQUE,
                    manifest_json TEXT NOT NULL,
                    approval_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    backend_ref TEXT
                )
                """
            )

    def reserve(
        self,
        manifest: RunManifest,
        approval: ApprovalRecord,
    ) -> _Reservation:
        manifest_json = manifest.model_dump_json()
        approval_json = approval.model_dump_json()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT run_id, manifest_json, status, backend_ref
                FROM run_launches
                WHERE idempotency_key = ?
                """,
                (manifest.idempotency_key,),
            ).fetchone()
            if row is not None:
                if row[1] != manifest_json:
                    raise IdempotencyConflictError(
                        "idempotency key already belongs to a different manifest"
                    )
                return _Reservation(
                    submission=RunSubmission(
                        run_id=row[0],
                        idempotency_key=manifest.idempotency_key,
                        status=RunSubmissionStatus(row[2]),
                        backend_ref=row[3],
                        duplicate=True,
                    ),
                    created=False,
                )
            try:
                connection.execute(
                    """
                    INSERT INTO run_launches (
                        idempotency_key,
                        run_id,
                        manifest_json,
                        approval_json,
                        status,
                        backend_ref
                    ) VALUES (?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        manifest.idempotency_key,
                        manifest.run_id,
                        manifest_json,
                        approval_json,
                        RunSubmissionStatus.MANIFEST_RECORDED.value,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise IdempotencyConflictError(
                    "run_id or idempotency key is already reserved"
                ) from error
        return _Reservation(
            submission=RunSubmission(
                run_id=manifest.run_id,
                idempotency_key=manifest.idempotency_key,
                status=RunSubmissionStatus.MANIFEST_RECORDED,
            ),
            created=True,
        )

    def mark(
        self,
        idempotency_key: str,
        status: RunSubmissionStatus,
        backend_ref: str | None,
    ) -> RunSubmission:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE run_launches
                SET status = ?, backend_ref = ?
                WHERE idempotency_key = ?
                """,
                (status.value, backend_ref, idempotency_key),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown idempotency key: {idempotency_key}")
        submission = self.lookup(idempotency_key)
        if submission is None:
            raise RuntimeError("updated run reservation could not be reloaded")
        return submission

    def lookup(self, idempotency_key: str) -> RunSubmission | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT run_id, status, backend_ref
                FROM run_launches
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
        if row is None:
            return None
        return RunSubmission(
            run_id=row[0],
            idempotency_key=idempotency_key,
            status=RunSubmissionStatus(row[1]),
            backend_ref=row[2],
        )

    @contextmanager
    def _connection(self):
        with closing(sqlite3.connect(self._path)) as connection:
            with connection:
                yield connection


class ManifestFirstRunner:
    def __init__(
        self,
        registry: SQLiteRunRegistry,
        backend: RunnerBackend,
    ) -> None:
        self._registry = registry
        self._backend = backend

    def submit(
        self,
        manifest: RunManifest,
        approval: ApprovalRecord,
    ) -> RunSubmission:
        _validate_approval(manifest, approval)
        reservation = self._registry.reserve(manifest, approval)
        if not reservation.created:
            return reservation.submission

        try:
            backend_ref = self._backend.launch(manifest)
            if not isinstance(backend_ref, str) or not backend_ref.strip():
                raise RuntimeError("runner backend returned an invalid reference")
        except Exception as error:
            self._registry.mark(
                manifest.idempotency_key,
                RunSubmissionStatus.LAUNCH_UNKNOWN,
                None,
            )
            raise RunLaunchUncertainError(manifest.run_id) from error

        return self._registry.mark(
            manifest.idempotency_key,
            RunSubmissionStatus.LAUNCHED,
            backend_ref,
        )


def _validate_approval(
    manifest: RunManifest,
    approval: ApprovalRecord,
) -> None:
    if approval.kind is not ApprovalKind.EXPERIMENT:
        raise ValueError("runner requires an EXPERIMENT approval")
    if approval.decision is not ApprovalDecision.APPROVED:
        raise ValueError("runner requires an approved decision")
    if approval.workflow_id != manifest.workflow_id:
        raise ValueError("approval workflow_id must match RunManifest")

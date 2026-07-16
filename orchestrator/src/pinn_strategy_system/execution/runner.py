"""Manifest-first execution lifecycle with explicit backend reconciliation."""

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
    ArtifactCollectionReport,
    ArtifactCollectionSpec,
    ArtifactCollectionStatus,
    BackendRunPhase,
    BackendRunRef,
    BackendRunStatus,
    ExecutionRequest,
    PreparedRun,
    RunCancellationRequest,
    RunManifest,
    RunSubmission,
    RunSubmissionStatus,
)


class ExecutionBackend(Protocol):
    def prepare(self, request: ExecutionRequest) -> PreparedRun: ...

    def launch(self, prepared_run: PreparedRun) -> BackendRunRef: ...

    def reconcile(self, backend_ref: BackendRunRef) -> BackendRunStatus: ...

    def cancel(
        self,
        backend_ref: BackendRunRef,
        request: RunCancellationRequest,
    ) -> BackendRunStatus: ...

    def collect(
        self,
        backend_ref: BackendRunRef,
        spec: ArtifactCollectionSpec,
    ) -> ArtifactCollectionReport: ...


class IdempotencyConflictError(RuntimeError):
    pass


class RunRegistrySchemaError(RuntimeError):
    pass


class RunPreparationError(RuntimeError):
    def __init__(self, run_id: str) -> None:
        super().__init__(f"execution preparation failed for {run_id}")
        self.run_id = run_id


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


@dataclass(frozen=True)
class _StoredRun:
    manifest: RunManifest
    approval: ApprovalRecord
    submission: RunSubmission


class SQLiteRunRegistry:
    """Own execution lifecycle metadata; artifacts remain in their store."""

    def __init__(self, database_path: str | Path) -> None:
        path = Path(database_path)
        if not path.is_absolute():
            raise ValueError("run registry path must be absolute")
        if not path.parent.exists():
            raise ValueError("run registry parent directory must already exist")
        self._path = str(path)
        with self._connection() as connection:
            legacy = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'run_launches'
                """
            ).fetchone()
            if legacy is not None:
                raise RunRegistrySchemaError(
                    "launch-only registry detected; use a new lifecycle database "
                    "or an explicitly governed migration"
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_runs_v2 (
                    idempotency_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL UNIQUE,
                    manifest_json TEXT NOT NULL,
                    approval_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    prepared_json TEXT,
                    backend_ref_json TEXT,
                    backend_status_json TEXT,
                    collection_report_json TEXT
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
            row = self._select(connection, manifest.idempotency_key)
            if row is not None:
                if row[2] != manifest_json or row[3] != approval_json:
                    raise IdempotencyConflictError(
                        "idempotency key already belongs to different governed inputs"
                    )
                return _Reservation(
                    submission=self._stored_from_row(row).submission.model_copy(
                        update={"duplicate": True}
                    ),
                    created=False,
                )
            try:
                connection.execute(
                    """
                    INSERT INTO execution_runs_v2 (
                        idempotency_key,
                        run_id,
                        manifest_json,
                        approval_json,
                        status,
                        prepared_json,
                        backend_ref_json,
                        backend_status_json,
                        collection_report_json
                    ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
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

    def transition(
        self,
        idempotency_key: str,
        status: RunSubmissionStatus,
        *,
        prepared_run: PreparedRun | None = None,
        backend_ref: BackendRunRef | None = None,
        backend_status: BackendRunStatus | None = None,
        collection_report: ArtifactCollectionReport | None = None,
    ) -> RunSubmission:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._select(connection, idempotency_key)
            if row is None:
                raise KeyError(f"unknown idempotency key: {idempotency_key}")
            stored = self._stored_from_row(row)
            current = stored.submission.status
            if not _transition_allowed(current, status):
                raise ValueError(
                    f"invalid run transition: {current.value} -> {status.value}"
                )
            prepared = prepared_run or stored.submission.prepared_run
            reference = backend_ref or stored.submission.backend_ref
            observed = backend_status or stored.submission.last_backend_status
            collected = collection_report or stored.submission.collection_report
            submission = RunSubmission(
                run_id=stored.manifest.run_id,
                idempotency_key=idempotency_key,
                status=status,
                prepared_run=prepared,
                backend_ref=reference,
                last_backend_status=observed,
                collection_report=collected,
            )
            connection.execute(
                """
                UPDATE execution_runs_v2
                SET status = ?, prepared_json = ?, backend_ref_json = ?,
                    backend_status_json = ?, collection_report_json = ?
                WHERE idempotency_key = ?
                """,
                (
                    status.value,
                    _json_or_none(prepared),
                    _json_or_none(reference),
                    _json_or_none(observed),
                    _json_or_none(collected),
                    idempotency_key,
                ),
            )
        return submission

    def lookup(self, idempotency_key: str) -> RunSubmission | None:
        with self._connection() as connection:
            row = self._select(connection, idempotency_key)
        if row is None:
            return None
        return self._stored_from_row(row).submission

    def manifest_for(self, idempotency_key: str) -> RunManifest:
        with self._connection() as connection:
            row = self._select(connection, idempotency_key)
        if row is None:
            raise KeyError(f"unknown idempotency key: {idempotency_key}")
        return self._stored_from_row(row).manifest

    @staticmethod
    def _select(connection: sqlite3.Connection, idempotency_key: str):
        return connection.execute(
            """
            SELECT idempotency_key, run_id, manifest_json, approval_json,
                   status, prepared_json, backend_ref_json,
                   backend_status_json, collection_report_json
            FROM execution_runs_v2
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()

    @staticmethod
    def _stored_from_row(row: tuple) -> _StoredRun:
        prepared = _model_or_none(PreparedRun, row[5])
        backend_ref = _model_or_none(BackendRunRef, row[6])
        backend_status = _model_or_none(BackendRunStatus, row[7])
        collection_report = _model_or_none(ArtifactCollectionReport, row[8])
        return _StoredRun(
            manifest=RunManifest.model_validate_json(row[2]),
            approval=ApprovalRecord.model_validate_json(row[3]),
            submission=RunSubmission(
                run_id=row[1],
                idempotency_key=row[0],
                status=RunSubmissionStatus(row[4]),
                prepared_run=prepared,
                backend_ref=backend_ref,
                last_backend_status=backend_status,
                collection_report=collection_report,
            ),
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
        backend: ExecutionBackend,
    ) -> None:
        self._registry = registry
        self._backend = backend

    def submit(
        self,
        manifest: RunManifest,
        approval: ApprovalRecord,
    ) -> RunSubmission:
        _validate_launch_approval(manifest, approval)
        reservation = self._registry.reserve(manifest, approval)
        if not reservation.created:
            return reservation.submission

        request = ExecutionRequest(
            request_id=f"execution-{manifest.run_id}",
            manifest=manifest,
            approval=approval,
        )
        try:
            prepared = self._backend.prepare(request)
            _validate_prepared_run(request, prepared)
        except Exception as error:
            self._registry.transition(
                manifest.idempotency_key,
                RunSubmissionStatus.FAILED,
            )
            raise RunPreparationError(manifest.run_id) from error

        self._registry.transition(
            manifest.idempotency_key,
            RunSubmissionStatus.PREPARED,
            prepared_run=prepared,
            backend_ref=prepared.backend_ref,
        )
        try:
            backend_ref = self._backend.launch(prepared)
            if backend_ref != prepared.backend_ref:
                raise RuntimeError("backend launch returned an unexpected reference")
        except Exception as error:
            self._registry.transition(
                manifest.idempotency_key,
                RunSubmissionStatus.RUNNING_UNKNOWN,
                prepared_run=prepared,
                backend_ref=prepared.backend_ref,
            )
            raise RunLaunchUncertainError(manifest.run_id) from error

        return self._registry.transition(
            manifest.idempotency_key,
            RunSubmissionStatus.RUNNING,
            prepared_run=prepared,
            backend_ref=backend_ref,
        )

    def reconcile(self, idempotency_key: str) -> RunSubmission:
        submission = _require_submission(self._registry, idempotency_key)
        backend_ref = _require_backend_ref(submission)
        status = self._backend.reconcile(backend_ref)
        _validate_backend_status(backend_ref, status)
        return self._registry.transition(
            idempotency_key,
            RunSubmissionStatus(status.phase.value),
            backend_status=status,
        )

    def cancel(
        self,
        idempotency_key: str,
        request: RunCancellationRequest,
    ) -> RunSubmission:
        submission = _require_submission(self._registry, idempotency_key)
        manifest = self._registry.manifest_for(idempotency_key)
        _validate_cancellation(manifest, request)
        backend_ref = _require_backend_ref(submission)
        self._registry.transition(
            idempotency_key,
            RunSubmissionStatus.CANCELLING,
        )
        try:
            status = self._backend.cancel(backend_ref, request)
            _validate_backend_status(backend_ref, status)
            allowed = (
                BackendRunPhase.CANCELLING,
                BackendRunPhase.CANCELLED,
                BackendRunPhase.RUNNING_UNKNOWN,
                BackendRunPhase.FAILED,
            )
            if status.phase not in allowed:
                raise RuntimeError("backend returned an invalid cancellation phase")
        except Exception:
            self._registry.transition(
                idempotency_key,
                RunSubmissionStatus.RUNNING_UNKNOWN,
            )
            raise
        return self._registry.transition(
            idempotency_key,
            RunSubmissionStatus(status.phase.value),
            backend_status=status,
        )

    def collect(
        self,
        idempotency_key: str,
        spec: ArtifactCollectionSpec,
    ) -> RunSubmission:
        submission = _require_submission(self._registry, idempotency_key)
        if submission.status is not RunSubmissionStatus.COMPLETED:
            raise ValueError("artifact collection requires a completed run")
        backend_ref = _require_backend_ref(submission)
        if spec.run_id != submission.run_id or spec.backend_ref != backend_ref:
            raise ValueError("artifact collection spec does not match submission")
        self._registry.transition(
            idempotency_key,
            RunSubmissionStatus.COLLECTING,
        )
        try:
            report = self._backend.collect(backend_ref, spec)
            if report.run_id != submission.run_id:
                raise RuntimeError("artifact collection report run_id mismatch")
        except Exception:
            self._registry.transition(
                idempotency_key,
                RunSubmissionStatus.FAILED,
            )
            raise
        target = (
            RunSubmissionStatus.COMPLETED
            if report.status is ArtifactCollectionStatus.COMPLETE
            else RunSubmissionStatus.FAILED
        )
        return self._registry.transition(
            idempotency_key,
            target,
            collection_report=report,
        )


def _validate_launch_approval(
    manifest: RunManifest,
    approval: ApprovalRecord,
) -> None:
    if approval.kind is not ApprovalKind.EXPERIMENT:
        raise ValueError("runner requires an EXPERIMENT approval")
    if approval.decision is not ApprovalDecision.APPROVED:
        raise ValueError("runner requires an approved decision")
    if approval.workflow_id != manifest.workflow_id:
        raise ValueError("approval workflow_id must match RunManifest")


def _validate_prepared_run(
    request: ExecutionRequest,
    prepared: PreparedRun,
) -> None:
    if prepared.request != request:
        raise ValueError("backend prepared different governed inputs")
    if prepared.backend_ref.run_id != request.manifest.run_id:
        raise ValueError("prepared backend reference run_id mismatch")
    if prepared.backend_ref.idempotency_key != request.manifest.idempotency_key:
        raise ValueError("prepared backend reference idempotency_key mismatch")


def _validate_backend_status(
    backend_ref: BackendRunRef,
    status: BackendRunStatus,
) -> None:
    if status.backend_ref != backend_ref:
        raise RuntimeError("backend status reference mismatch")


def _validate_cancellation(
    manifest: RunManifest,
    request: RunCancellationRequest,
) -> None:
    if request.run_id != manifest.run_id:
        raise ValueError("cancellation run_id must match RunManifest")
    if request.workflow_id != manifest.workflow_id:
        raise ValueError("cancellation workflow_id must match RunManifest")


def _require_submission(
    registry: SQLiteRunRegistry,
    idempotency_key: str,
) -> RunSubmission:
    submission = registry.lookup(idempotency_key)
    if submission is None:
        raise KeyError(f"unknown idempotency key: {idempotency_key}")
    return submission


def _require_backend_ref(submission: RunSubmission) -> BackendRunRef:
    if submission.backend_ref is None:
        raise ValueError("run has no backend reference to reconcile")
    return submission.backend_ref


def _transition_allowed(
    current: RunSubmissionStatus,
    target: RunSubmissionStatus,
) -> bool:
    transitions = (
        (
            RunSubmissionStatus.MANIFEST_RECORDED,
            (RunSubmissionStatus.PREPARED, RunSubmissionStatus.FAILED),
        ),
        (
            RunSubmissionStatus.PREPARED,
            (
                RunSubmissionStatus.RUNNING,
                RunSubmissionStatus.RUNNING_UNKNOWN,
                RunSubmissionStatus.FAILED,
            ),
        ),
        (
            RunSubmissionStatus.RUNNING,
            (
                RunSubmissionStatus.RUNNING_UNKNOWN,
                RunSubmissionStatus.CANCELLING,
                RunSubmissionStatus.CANCELLED,
                RunSubmissionStatus.COMPLETED,
                RunSubmissionStatus.FAILED,
            ),
        ),
        (
            RunSubmissionStatus.RUNNING_UNKNOWN,
            (
                RunSubmissionStatus.RUNNING,
                RunSubmissionStatus.CANCELLING,
                RunSubmissionStatus.CANCELLED,
                RunSubmissionStatus.COMPLETED,
                RunSubmissionStatus.FAILED,
            ),
        ),
        (
            RunSubmissionStatus.CANCELLING,
            (
                RunSubmissionStatus.RUNNING_UNKNOWN,
                RunSubmissionStatus.CANCELLED,
                RunSubmissionStatus.FAILED,
            ),
        ),
        (
            RunSubmissionStatus.COMPLETED,
            (RunSubmissionStatus.COLLECTING,),
        ),
        (
            RunSubmissionStatus.COLLECTING,
            (RunSubmissionStatus.COMPLETED, RunSubmissionStatus.FAILED),
        ),
        (RunSubmissionStatus.CANCELLED, ()),
        (RunSubmissionStatus.FAILED, ()),
    )
    if current is target:
        return True
    return any(
        source is current and target in destinations
        for source, destinations in transitions
    )


def _json_or_none(model) -> str | None:
    return None if model is None else model.model_dump_json()


def _model_or_none(model_type, payload: str | None):
    return None if payload is None else model_type.model_validate_json(payload)

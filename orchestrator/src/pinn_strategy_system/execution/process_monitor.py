"""Read-only psutil sampler restricted to explicitly registered processes."""

from __future__ import annotations

import math
from datetime import datetime

import psutil
from pydantic import Field

from pinn_strategy_system.contracts import RunEvent, RunEventType, VersionedModel


class ApprovedProcessIdentity(VersionedModel):
    run_id: str = Field(min_length=1, max_length=256)
    pid: int = Field(gt=0)
    expected_create_time: float = Field(allow_inf_nan=False, gt=0)
    approval_id: str = Field(min_length=1, max_length=256)


class ProcessUnavailableError(RuntimeError):
    pass


class ApprovedProcessSampler:
    def __init__(
        self,
        approved_processes: tuple[ApprovedProcessIdentity, ...],
    ) -> None:
        run_ids = tuple(item.run_id for item in approved_processes)
        pids = tuple(item.pid for item in approved_processes)
        if len(set(run_ids)) != len(run_ids):
            raise ValueError("approved process run_id values must be unique")
        if len(set(pids)) != len(pids):
            raise ValueError("one PID cannot belong to multiple approved runs")
        self._approved = {
            item.run_id: item
            for item in approved_processes
        }

    def capture(
        self,
        *,
        event_id: str,
        run_id: str,
        occurred_at: datetime,
    ) -> RunEvent:
        if occurred_at.tzinfo is None:
            raise ValueError("resource event timestamp must be timezone-aware")
        identity = self._approved.get(run_id)
        if identity is None:
            raise PermissionError(f"run has no approved process identity: {run_id}")
        try:
            process = psutil.Process(identity.pid)
            actual_create_time = process.create_time()
            if not math.isclose(
                actual_create_time,
                identity.expected_create_time,
                rel_tol=0.0,
                abs_tol=1e-3,
            ):
                raise ProcessUnavailableError(
                    "PID was reused by a process outside the approved identity"
                )
            with process.oneshot():
                memory = process.memory_info()
                cpu = process.cpu_times()
                status = process.status()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as error:
            raise ProcessUnavailableError(
                f"approved process is unavailable: {run_id}"
            ) from error
        return RunEvent(
            event_id=event_id,
            run_id=run_id,
            event_type=RunEventType.RESOURCE_UPDATED,
            occurred_at=occurred_at,
            payload={
                "approval_id": identity.approval_id,
                "pid": identity.pid,
                "create_time": actual_create_time,
                "rss_bytes": int(memory.rss),
                "vms_bytes": int(memory.vms),
                "cpu_user_seconds": float(cpu.user),
                "cpu_system_seconds": float(cpu.system),
                "status": status,
            },
        )

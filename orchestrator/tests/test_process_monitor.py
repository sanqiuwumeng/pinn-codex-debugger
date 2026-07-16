from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

import psutil

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.contracts import (  # noqa: E402
    RunEventType,
)
from pinn_strategy_system.execution import (  # noqa: E402
    ApprovedProcessIdentity,
    ApprovedProcessSampler,
    ProcessUnavailableError,
)


class ProcessMonitorTests(unittest.TestCase):
    def test_sampler_reads_only_an_explicit_process_identity(self) -> None:
        process = psutil.Process()
        sampler = ApprovedProcessSampler(
            (
                ApprovedProcessIdentity(
                    run_id="run-current-test",
                    pid=process.pid,
                    expected_create_time=process.create_time(),
                    approval_id="approval-1",
                ),
            )
        )
        event = sampler.capture(
            event_id="resource-1",
            run_id="run-current-test",
            occurred_at=datetime(2026, 7, 16, tzinfo=UTC),
        )
        self.assertEqual(event.event_type, RunEventType.RESOURCE_UPDATED)
        self.assertEqual(event.payload["pid"], process.pid)
        self.assertGreater(event.payload["rss_bytes"], 0)
        self.assertEqual(event.payload["approval_id"], "approval-1")

    def test_unapproved_run_and_reused_pid_identity_are_rejected(self) -> None:
        process = psutil.Process()
        sampler = ApprovedProcessSampler(
            (
                ApprovedProcessIdentity(
                    run_id="run-approved",
                    pid=process.pid,
                    expected_create_time=process.create_time() + 10.0,
                    approval_id="approval-1",
                ),
            )
        )
        with self.assertRaises(PermissionError):
            sampler.capture(
                event_id="resource-unapproved",
                run_id="run-unapproved",
                occurred_at=datetime(2026, 7, 16, tzinfo=UTC),
            )
        with self.assertRaisesRegex(ProcessUnavailableError, "PID was reused"):
            sampler.capture(
                event_id="resource-reused",
                run_id="run-approved",
                occurred_at=datetime(2026, 7, 16, tzinfo=UTC),
            )


if __name__ == "__main__":
    unittest.main()

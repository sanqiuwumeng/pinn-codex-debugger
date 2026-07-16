from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.assurance import EventMonitor  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    ArtifactRef,
    MonitorOutcome,
    MonitoringPolicy,
    RunEvent,
    RunEventType,
)

SHA = "6" * 64
START = datetime(2026, 7, 15, 8, 0, tzinfo=UTC)


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://monitor/{name}",
        sha256=SHA,
    )


def event(
    event_id: str,
    event_type: RunEventType,
    seconds: int,
    *,
    payload=None,
    artifacts=(),
) -> RunEvent:
    return RunEvent(
        event_id=event_id,
        run_id="run-1",
        event_type=event_type,
        occurred_at=START + timedelta(seconds=seconds),
        payload=payload or {},
        artifact_refs=artifacts,
    )


def policy() -> MonitoringPolicy:
    return MonitoringPolicy(
        policy_id="monitor-v1",
        log_stall_seconds=60,
        required_artifact_ids=("metrics", "checkpoint"),
        metric_upper_bounds={"loss": 100.0},
    )


class EventMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.monitor = EventMonitor()

    def test_normal_metric_and_resource_events_do_not_trigger_agent(self) -> None:
        report = self.monitor.evaluate(
            report_id="healthy",
            run_id="run-1",
            events=(
                event("start", RunEventType.RUN_STARTED, 0),
                event(
                    "metric",
                    RunEventType.METRIC_UPDATED,
                    10,
                    payload={"metric": "loss", "value": 10.0},
                ),
                event("resource", RunEventType.RESOURCE_UPDATED, 20),
            ),
            policy=policy(),
            now=START + timedelta(seconds=30),
        )
        self.assertEqual(report.outcome, MonitorOutcome.HEALTHY)
        self.assertFalse(report.trigger_agent)

    def test_nan_and_metric_threshold_are_anomalies(self) -> None:
        report = self.monitor.evaluate(
            report_id="anomaly",
            run_id="run-1",
            events=(
                event("start", RunEventType.RUN_STARTED, 0),
                event(
                    "metric",
                    RunEventType.METRIC_UPDATED,
                    10,
                    payload={"metric": "loss", "value": 1000.0},
                ),
                event("nan", RunEventType.NAN_DETECTED, 11),
            ),
            policy=policy(),
            now=START + timedelta(seconds=12),
        )
        self.assertEqual(report.outcome, MonitorOutcome.ANOMALY)
        self.assertTrue(report.trigger_agent)
        self.assertTrue(any("NAN_DETECTED" in item for item in report.reasons))
        self.assertTrue(any("upper bound" in item for item in report.reasons))

    def test_stalled_event_stream_is_anomaly(self) -> None:
        report = self.monitor.evaluate(
            report_id="stalled",
            run_id="run-1",
            events=(event("start", RunEventType.RUN_STARTED, 0),),
            policy=policy(),
            now=START + timedelta(seconds=61),
        )
        self.assertEqual(report.outcome, MonitorOutcome.ANOMALY)
        self.assertTrue(any("stalled" in item for item in report.reasons))

    def test_completion_requires_declared_artifacts(self) -> None:
        missing = self.monitor.evaluate(
            report_id="missing",
            run_id="run-1",
            events=(
                event("start", RunEventType.RUN_STARTED, 0),
                event(
                    "finish",
                    RunEventType.RUN_FINISHED,
                    20,
                    artifacts=(artifact("metrics"),),
                ),
            ),
            policy=policy(),
            now=START + timedelta(seconds=20),
        )
        self.assertEqual(missing.outcome, MonitorOutcome.ANOMALY)
        self.assertTrue(any("checkpoint" in item for item in missing.reasons))

        complete = self.monitor.evaluate(
            report_id="complete",
            run_id="run-1",
            events=(
                event("start", RunEventType.RUN_STARTED, 0),
                event(
                    "finish",
                    RunEventType.RUN_FINISHED,
                    20,
                    artifacts=(artifact("metrics"), artifact("checkpoint")),
                ),
            ),
            policy=policy(),
            now=START + timedelta(seconds=20),
        )
        self.assertEqual(complete.outcome, MonitorOutcome.COMPLETED)
        self.assertTrue(complete.trigger_agent)

    def test_checkpoint_is_a_milestone_not_continuous_agent_work(self) -> None:
        report = self.monitor.evaluate(
            report_id="checkpoint",
            run_id="run-1",
            events=(
                event("start", RunEventType.RUN_STARTED, 0),
                event("checkpoint", RunEventType.CHECKPOINT_WRITTEN, 10),
            ),
            policy=policy(),
            now=START + timedelta(seconds=20),
        )
        self.assertEqual(report.outcome, MonitorOutcome.MILESTONE)
        self.assertTrue(report.trigger_agent)


if __name__ == "__main__":
    unittest.main()

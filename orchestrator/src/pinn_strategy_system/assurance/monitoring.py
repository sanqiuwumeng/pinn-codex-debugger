"""Deterministic event evaluation; Agents see only anomalies and milestones."""

from __future__ import annotations

from datetime import datetime

from pinn_strategy_system.contracts import (
    MonitorOutcome,
    MonitoringPolicy,
    MonitoringReport,
    RunEvent,
    RunEventType,
)


class EventMonitor:
    def evaluate(
        self,
        *,
        report_id: str,
        run_id: str,
        events: tuple[RunEvent, ...],
        policy: MonitoringPolicy,
        now: datetime,
    ) -> MonitoringReport:
        if any(event.run_id != run_id for event in events):
            raise ValueError("all events must belong to the monitored run")
        ordered = tuple(sorted(events, key=lambda event: event.occurred_at))
        if ordered and (ordered[-1].occurred_at.tzinfo is None) != (
            now.tzinfo is None
        ):
            raise ValueError("event and monitor timestamps must share timezone semantics")

        event_types = {event.event_type for event in ordered}
        observed_artifacts = tuple(
            dict.fromkeys(
                artifact.artifact_id
                for event in ordered
                for artifact in event.artifact_refs
            )
        )
        reasons: list[str] = []

        if RunEventType.RUN_FAILED in event_types:
            reasons.append("runner emitted RUN_FAILED")
            return _report(
                report_id,
                run_id,
                MonitorOutcome.FAILED,
                reasons,
                ordered,
                observed_artifacts,
            )

        anomaly_names = sorted(
            event_type.value
            for event_type in event_types
            if event_type in policy.anomaly_event_types
        )
        reasons.extend(f"anomaly event: {name}" for name in anomaly_names)
        reasons.extend(_metric_threshold_reasons(ordered, policy))

        finished = RunEventType.RUN_FINISHED in event_types
        started = RunEventType.RUN_STARTED in event_types
        if started and not finished and ordered:
            elapsed = (now - ordered[-1].occurred_at).total_seconds()
            if elapsed > policy.log_stall_seconds:
                reasons.append(
                    f"event stream stalled for {elapsed} seconds; "
                    f"limit={policy.log_stall_seconds}"
                )

        missing_artifacts = tuple(
            artifact_id
            for artifact_id in policy.required_artifact_ids
            if artifact_id not in observed_artifacts
        )
        if finished:
            reasons.extend(
                f"required artifact missing at completion: {artifact_id}"
                for artifact_id in missing_artifacts
            )

        if reasons:
            return _report(
                report_id,
                run_id,
                MonitorOutcome.ANOMALY,
                reasons,
                ordered,
                observed_artifacts,
            )
        if finished:
            return _report(
                report_id,
                run_id,
                MonitorOutcome.COMPLETED,
                ("run reached a declared completion milestone",),
                ordered,
                observed_artifacts,
            )
        milestones = sorted(
            event_type.value
            for event_type in event_types
            if event_type in policy.milestone_event_types
        )
        if milestones:
            return _report(
                report_id,
                run_id,
                MonitorOutcome.MILESTONE,
                tuple(f"milestone event: {name}" for name in milestones),
                ordered,
                observed_artifacts,
            )
        return _report(
            report_id,
            run_id,
            MonitorOutcome.HEALTHY,
            (),
            ordered,
            observed_artifacts,
        )


def _metric_threshold_reasons(
    events: tuple[RunEvent, ...],
    policy: MonitoringPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for event in events:
        if event.event_type is not RunEventType.METRIC_UPDATED:
            continue
        metric = event.payload.get("metric")
        value = event.payload.get("value")
        if not isinstance(metric, str):
            continue
        threshold = policy.metric_upper_bounds.get(metric)
        if threshold is None:
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if float(value) > threshold:
                reasons.append(
                    f"metric {metric}={value} exceeds upper bound {threshold}"
                )
    return tuple(reasons)


def _report(
    report_id: str,
    run_id: str,
    outcome: MonitorOutcome,
    reasons: tuple[str, ...] | list[str],
    events: tuple[RunEvent, ...],
    observed_artifacts: tuple[str, ...],
) -> MonitoringReport:
    return MonitoringReport(
        report_id=report_id,
        run_id=run_id,
        outcome=outcome,
        trigger_agent=outcome is not MonitorOutcome.HEALTHY,
        reasons=tuple(reasons),
        last_event_at=events[-1].occurred_at if events else None,
        observed_artifact_ids=observed_artifacts,
    )

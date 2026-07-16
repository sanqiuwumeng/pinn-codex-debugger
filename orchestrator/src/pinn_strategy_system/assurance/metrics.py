"""User-governed metric readiness and deterministic comparison policy."""

from __future__ import annotations

from dataclasses import dataclass

from pinn_strategy_system.contracts import (
    AggregationPolicy,
    DecisionRecord,
    DecisionStatus,
    MetricContract,
    MetricDirection,
    MetricRole,
    MetricRule,
    MetricValueSet,
)


@dataclass(frozen=True)
class MetricPreferenceResult:
    ready: bool
    reasons: tuple[str, ...]


class MetricDecisionService:
    """Apply a MetricContract without inventing priorities or scalar weights."""

    def __init__(self, *, comparison_tolerance: float = 1e-12) -> None:
        if comparison_tolerance < 0:
            raise ValueError("comparison_tolerance must be nonnegative")
        self._tolerance = comparison_tolerance

    def preference_readiness(
        self,
        contract: MetricContract | None,
    ) -> MetricPreferenceResult:
        if contract is None:
            return MetricPreferenceResult(
                ready=False,
                reasons=(
                    "physical-model authority, evidence basis, primary metrics and "
                    "guardrails have not been confirmed by the user",
                ),
            )
        return MetricPreferenceResult(ready=True, reasons=())

    def compare(
        self,
        *,
        decision_id: str,
        contract: MetricContract | None,
        baseline: MetricValueSet,
        candidate: MetricValueSet,
        observed_failure_mechanism: str,
    ) -> DecisionRecord:
        readiness = self.preference_readiness(contract)
        if not readiness.ready or contract is None:
            return self._decision(
                decision_id,
                DecisionStatus.NEEDS_EVIDENCE,
                observed_failure_mechanism,
                readiness.reasons,
            )

        missing = self._missing_required(contract, baseline, candidate)
        if missing:
            return self._decision(
                decision_id,
                DecisionStatus.NEEDS_EVIDENCE,
                observed_failure_mechanism,
                tuple(f"required metric is missing: {name}" for name in missing),
            )

        hard_failures = tuple(
            reason
            for rule in contract.metrics
            if rule.role is MetricRole.HARD_CONSTRAINT
            for reason in self._absolute_threshold_failures(rule, candidate)
        )
        if hard_failures:
            return self._decision(
                decision_id,
                DecisionStatus.REJECT,
                observed_failure_mechanism,
                hard_failures,
            )

        primary_status, primary_reasons = self._compare_primary(
            contract,
            baseline,
            candidate,
        )
        if primary_status is not DecisionStatus.ACCEPT:
            return self._decision(
                decision_id,
                primary_status,
                observed_failure_mechanism,
                primary_reasons,
            )

        guardrail_failures = tuple(
            reason
            for rule in contract.metrics
            if rule.role is MetricRole.GUARDRAIL
            for reason in self._guardrail_failures(rule, baseline, candidate)
        )
        if guardrail_failures:
            return self._decision(
                decision_id,
                DecisionStatus.REJECT,
                observed_failure_mechanism,
                (*primary_reasons, *guardrail_failures),
            )

        diagnostic_notes = tuple(
            (
                f"diagnostic {rule.name}: baseline={baseline.values[rule.name]}, "
                f"candidate={candidate.values[rule.name]}"
            )
            for rule in contract.metrics
            if rule.role in {MetricRole.SECONDARY, MetricRole.DIAGNOSTIC}
            and rule.name in baseline.values
            and rule.name in candidate.values
        )
        return self._decision(
            decision_id,
            DecisionStatus.ACCEPT,
            observed_failure_mechanism,
            (*primary_reasons, *diagnostic_notes),
        )

    def _missing_required(
        self,
        contract: MetricContract,
        baseline: MetricValueSet,
        candidate: MetricValueSet,
    ) -> tuple[str, ...]:
        return tuple(
            rule.name
            for rule in contract.metrics
            if rule.required
            and (
                rule.name not in baseline.values
                or rule.name not in candidate.values
            )
        )

    def _absolute_threshold_failures(
        self,
        rule: MetricRule,
        candidate: MetricValueSet,
    ) -> tuple[str, ...]:
        if rule.threshold is None:
            return ()
        value = candidate.values[rule.name]
        if _meets_threshold(value, rule.threshold, rule.direction, self._tolerance):
            return ()
        return (
            f"hard constraint {rule.name} failed: candidate={value}, "
            f"threshold={rule.threshold}, direction={rule.direction.value}",
        )

    def _compare_primary(
        self,
        contract: MetricContract,
        baseline: MetricValueSet,
        candidate: MetricValueSet,
    ) -> tuple[DecisionStatus, tuple[str, ...]]:
        rules = {rule.name: rule for rule in contract.metrics}
        ordered = tuple(rules[name] for name in contract.primary_order)

        if contract.aggregation_policy is AggregationPolicy.LEXICOGRAPHIC:
            for rule in ordered:
                comparison = _oriented_delta(
                    baseline.values[rule.name],
                    candidate.values[rule.name],
                    rule.direction,
                )
                if comparison > self._tolerance:
                    return (
                        DecisionStatus.ACCEPT,
                        (f"primary {rule.name} improved under lexicographic order",),
                    )
                if comparison < -self._tolerance:
                    return (
                        DecisionStatus.REJECT,
                        (f"primary {rule.name} regressed under lexicographic order",),
                    )
            return (
                DecisionStatus.REJECT,
                ("no primary metric improved beyond comparison tolerance",),
            )

        if contract.aggregation_policy is AggregationPolicy.PARETO:
            deltas = {
                rule.name: _oriented_delta(
                    baseline.values[rule.name],
                    candidate.values[rule.name],
                    rule.direction,
                )
                for rule in ordered
            }
            regressed = tuple(
                name for name, delta in deltas.items() if delta < -self._tolerance
            )
            if regressed:
                return (
                    DecisionStatus.REJECT,
                    (f"Pareto primary metrics regressed: {', '.join(regressed)}",),
                )
            if not any(delta > self._tolerance for delta in deltas.values()):
                return (
                    DecisionStatus.REJECT,
                    ("no Pareto primary metric improved",),
                )
            return (
                DecisionStatus.ACCEPT,
                ("candidate Pareto-dominates the baseline primary metrics",),
            )

        baseline_score = 0.0
        candidate_score = 0.0
        for rule in ordered:
            weight = rule.weight
            if weight is None:
                raise ValueError("validated scalar contract is missing a weight")
            orientation = 1.0 if rule.direction is MetricDirection.MAXIMIZE else -1.0
            baseline_score += weight * orientation * baseline.values[rule.name]
            candidate_score += weight * orientation * candidate.values[rule.name]
        if candidate_score <= baseline_score + self._tolerance:
            return (
                DecisionStatus.REJECT,
                ("user-authorized scalar primary score did not improve",),
            )
        return (
            DecisionStatus.ACCEPT,
            ("user-authorized scalar primary score improved",),
        )

    def _guardrail_failures(
        self,
        rule: MetricRule,
        baseline: MetricValueSet,
        candidate: MetricValueSet,
    ) -> tuple[str, ...]:
        failures = list(self._absolute_threshold_failures(rule, candidate))
        baseline_value = baseline.values[rule.name]
        candidate_value = candidate.values[rule.name]
        deterioration = (
            candidate_value - baseline_value
            if rule.direction is MetricDirection.MINIMIZE
            else baseline_value - candidate_value
        )
        if (
            rule.max_regression is not None
            and deterioration > rule.max_regression + self._tolerance
        ):
            failures.append(
                f"guardrail {rule.name} regressed by {deterioration}, "
                f"absolute_limit={rule.max_regression} {rule.unit}"
            )
        if rule.max_relative_regression is not None and deterioration > self._tolerance:
            scale = abs(baseline_value)
            relative_deterioration = (
                deterioration / scale
                if scale > self._tolerance
                else float("inf")
            )
            if relative_deterioration > (
                rule.max_relative_regression + self._tolerance
            ):
                failures.append(
                    f"guardrail {rule.name} regressed relatively by "
                    f"{relative_deterioration}, "
                    f"relative_limit={rule.max_relative_regression}"
                )
        return tuple(failures)

    @staticmethod
    def _decision(
        decision_id: str,
        status: DecisionStatus,
        mechanism: str,
        reasons: tuple[str, ...],
    ) -> DecisionRecord:
        return DecisionRecord(
            decision_id=decision_id,
            status=status,
            observed_failure_mechanism=mechanism,
            reasons=reasons,
        )


def _oriented_delta(
    baseline: float,
    candidate: float,
    direction: MetricDirection,
) -> float:
    if direction is MetricDirection.MINIMIZE:
        return baseline - candidate
    return candidate - baseline


def _meets_threshold(
    value: float,
    threshold: float,
    direction: MetricDirection,
    tolerance: float,
) -> bool:
    if direction is MetricDirection.MINIMIZE:
        return value <= threshold + tolerance
    return value >= threshold - tolerance

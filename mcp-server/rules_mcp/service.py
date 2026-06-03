"""Deterministic routing service with explicit injected dependencies."""

from __future__ import annotations

from .catalog import underspecified_rule
from .handbook import HandbookIndex
from .models import DiagnosisRequest, EvidenceMatch, SearchRequest, SymptomRecord, SymptomRule


class RulesRetrievalService:
    """Route symptoms and extract handbook evidence without hidden state."""

    def __init__(
        self,
        handbook_index: HandbookIndex,
        rules: tuple[SymptomRule, ...],
    ) -> None:
        self._handbook_index = handbook_index
        self._rules = rules

    @property
    def handbook_sha256(self) -> str:
        return self._handbook_index.source_sha256

    def diagnose(self, request: DiagnosisRequest) -> SymptomRecord:
        rule, matched_keywords = self._route(request.symptom)
        matches = self._handbook_index.search(
            query=request.symptom,
            anchors=rule.candidate_anchors,
            max_sections=request.max_sections,
        )
        return SymptomRecord(
            symptom=request.symptom,
            family=rule.family,
            matched_keywords=matched_keywords,
            evidence_received=request.evidence,
            evidence_gaps=rule.evidence_gaps,
            required_basic_checks=rule.required_basic_checks,
            candidate_anchors=rule.candidate_anchors,
            handbook_sha256=self._handbook_index.source_sha256,
            handbook_matches=matches,
            next_step_policy=(
                "Complete the relevant basic checks, then recommend at most one "
                "logical intervention with an expected metric and rollback condition."
            ),
        )

    def search(self, request: SearchRequest) -> tuple[EvidenceMatch, ...]:
        return self._handbook_index.search(
            query=request.query,
            anchors=request.anchors,
            max_sections=request.max_sections,
        )

    def _route(self, symptom: str) -> tuple[SymptomRule, tuple[str, ...]]:
        normalized_symptom = symptom.casefold()
        scored: list[tuple[int, int, SymptomRule, tuple[str, ...]]] = []

        for order, rule in enumerate(self._rules):
            matched = tuple(
                keyword
                for keyword in rule.keywords
                if keyword.casefold() in normalized_symptom
            )
            if matched:
                scored.append((len(matched), order, rule, matched))

        if not scored:
            return underspecified_rule(), ()

        scored.sort(key=lambda item: (-item[0], item[1]))
        _, _, rule, matched = scored[0]
        return rule, matched

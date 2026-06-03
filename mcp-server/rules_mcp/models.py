"""Explicit request and response models for deterministic handbook retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class HandbookSection:
    heading: str
    level: int
    line_start: int
    line_end: int
    text: str


@dataclass(frozen=True)
class SymptomRule:
    rule_id: str
    family: str
    keywords: tuple[str, ...]
    required_basic_checks: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    candidate_anchors: tuple[str, ...]


@dataclass(frozen=True)
class DiagnosisRequest:
    symptom: str
    evidence: tuple[str, ...] = ()
    max_sections: int = 3

    @classmethod
    def from_arguments(cls, arguments: dict[str, Any]) -> "DiagnosisRequest":
        symptom = arguments.get("symptom")
        if not isinstance(symptom, str) or not symptom.strip():
            raise ValueError("symptom must be a non-empty string")

        raw_evidence = arguments.get("evidence", [])
        if not isinstance(raw_evidence, list) or not all(
            isinstance(item, str) for item in raw_evidence
        ):
            raise ValueError("evidence must be an array of strings")

        max_sections = arguments.get("max_sections", 3)
        if not isinstance(max_sections, int) or not 1 <= max_sections <= 10:
            raise ValueError("max_sections must be an integer from 1 to 10")

        return cls(
            symptom=symptom.strip(),
            evidence=tuple(item.strip() for item in raw_evidence if item.strip()),
            max_sections=max_sections,
        )


@dataclass(frozen=True)
class SearchRequest:
    query: str
    anchors: tuple[str, ...] = ()
    max_sections: int = 5

    @classmethod
    def from_arguments(cls, arguments: dict[str, Any]) -> "SearchRequest":
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        raw_anchors = arguments.get("anchors", [])
        if not isinstance(raw_anchors, list) or not all(
            isinstance(item, str) for item in raw_anchors
        ):
            raise ValueError("anchors must be an array of strings")

        max_sections = arguments.get("max_sections", 5)
        if not isinstance(max_sections, int) or not 1 <= max_sections <= 10:
            raise ValueError("max_sections must be an integer from 1 to 10")

        return cls(
            query=query.strip(),
            anchors=tuple(item.strip() for item in raw_anchors if item.strip()),
            max_sections=max_sections,
        )


@dataclass(frozen=True)
class EvidenceMatch:
    heading: str
    line_start: int
    line_end: int
    matched_anchors: tuple[str, ...]
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SymptomRecord:
    symptom: str
    family: str
    matched_keywords: tuple[str, ...]
    evidence_received: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    required_basic_checks: tuple[str, ...]
    candidate_anchors: tuple[str, ...]
    handbook_sha256: str
    handbook_matches: tuple[EvidenceMatch, ...]
    next_step_policy: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["handbook_matches"] = [
            match.to_dict() for match in self.handbook_matches
        ]
        return payload

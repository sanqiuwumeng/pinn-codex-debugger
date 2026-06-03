"""Explicit models for hybrid handbook retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class HybridQuery:
    query: str
    evidence: tuple[str, ...] = ()
    anchors: tuple[str, ...] = ()
    max_sections: int = 5

    @classmethod
    def from_arguments(cls, arguments: dict[str, Any]) -> "HybridQuery":
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        raw_evidence = arguments.get("evidence", [])
        if not isinstance(raw_evidence, list) or not all(
            isinstance(item, str) for item in raw_evidence
        ):
            raise ValueError("evidence must be an array of strings")

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
            evidence=tuple(item.strip() for item in raw_evidence if item.strip()),
            anchors=tuple(item.strip() for item in raw_anchors if item.strip()),
            max_sections=max_sections,
        )


@dataclass(frozen=True)
class ScoreBreakdown:
    anchor: float
    concept: float
    lexical: float
    ngram: float
    heading: float
    specificity: float

    @property
    def total(self) -> float:
        return round(
            self.anchor
            + self.concept
            + self.lexical
            + self.ngram
            + self.heading
            + self.specificity,
            6,
        )

    def to_dict(self) -> dict[str, float]:
        payload = asdict(self)
        payload["total"] = self.total
        return payload


@dataclass(frozen=True)
class RankedSection:
    heading: str
    line_start: int
    line_end: int
    score: float
    score_parts: ScoreBreakdown
    matched_terms: tuple[str, ...]
    matched_concepts: tuple[str, ...]
    matched_anchors: tuple[str, ...]
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score_parts"] = self.score_parts.to_dict()
        return payload


@dataclass(frozen=True)
class HybridSearchResponse:
    query: str
    inferred_family: str
    rules_family: str
    matched_concepts: tuple[str, ...]
    source_sha256: str
    backend: str
    index_inputs: tuple[str, ...]
    ranked_sections: tuple[RankedSection, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ranked_sections"] = [
            section.to_dict() for section in self.ranked_sections
        ]
        return payload

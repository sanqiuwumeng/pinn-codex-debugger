"""Reproducible section index for hybrid retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rules_mcp.handbook import HandbookIndex, tokenize_query
from rules_mcp.models import HandbookSection

from .lexicon import Concept, concepts_for_text


@dataclass(frozen=True)
class SectionDocument:
    section: HandbookSection
    terms: frozenset[str]
    heading_terms: frozenset[str]
    concepts: frozenset[str]
    heading_concepts: frozenset[str]
    char_ngrams: frozenset[str]


@dataclass(frozen=True)
class HybridSectionIndex:
    source_sha256: str
    backend: str
    index_inputs: tuple[str, ...]
    documents: tuple[SectionDocument, ...]

    @classmethod
    def from_handbook(
        cls,
        handbook_index: HandbookIndex,
        concepts: tuple[Concept, ...],
    ) -> "HybridSectionIndex":
        documents = tuple(
            SectionDocument(
                section=section,
                terms=frozenset(_normalize_terms(tokenize_query(section.text))),
                heading_terms=frozenset(_normalize_terms(tokenize_query(section.heading))),
                concepts=frozenset(concepts_for_text(section.text, concepts)),
                heading_concepts=frozenset(concepts_for_text(section.heading, concepts)),
                char_ngrams=frozenset(character_ngrams(section.text)),
            )
            for section in handbook_index.sections
        )
        return cls(
            source_sha256=handbook_index.source_sha256,
            backend=(
                "stdlib-concept-charngram-v1:"
                "rules-anchor+concept-lexicon+token-overlap+char-3gram"
            ),
            index_inputs=(
                f"handbook_sha256={handbook_index.source_sha256}",
                f"section_count={len(handbook_index.sections)}",
                f"concept_count={len(concepts)}",
                "external_packages=none",
            ),
            documents=documents,
        )


def character_ngrams(text: str, size: int = 3) -> tuple[str, ...]:
    normalized = re.sub(r"\s+", "", text.casefold())
    if len(normalized) < size:
        return (normalized,) if normalized else ()
    return tuple(normalized[index : index + size] for index in range(len(normalized) - size + 1))


def normalized_query_terms(query: str) -> tuple[str, ...]:
    return _normalize_terms(tokenize_query(query))


def _normalize_terms(terms: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        normalized = term.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)

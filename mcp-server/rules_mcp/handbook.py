"""Byte-preserving handbook parsing and deterministic evidence extraction."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .models import EvidenceMatch, HandbookSection

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,}|[\u4e00-\u9fff]{2,}")


@dataclass(frozen=True)
class HandbookIndex:
    """Immutable searchable handbook index."""

    source_path: Path
    source_sha256: str
    sections: tuple[HandbookSection, ...]

    @classmethod
    def from_path(cls, source_path: Path) -> "HandbookIndex":
        raw_bytes = source_path.read_bytes()
        lines = raw_bytes.decode("utf-8").splitlines()
        headings: list[tuple[int, int, str]] = []

        for line_number, line in enumerate(lines, start=1):
            match = _HEADING_PATTERN.match(line)
            if match:
                headings.append((line_number, len(match.group(1)), match.group(2)))

        sections: list[HandbookSection] = []
        for index, (line_start, level, heading) in enumerate(headings):
            line_end = (
                headings[index + 1][0] - 1
                if index + 1 < len(headings)
                else len(lines)
            )
            text = "\n".join(lines[line_start - 1 : line_end])
            sections.append(
                HandbookSection(
                    heading=heading,
                    level=level,
                    line_start=line_start,
                    line_end=line_end,
                    text=text,
                )
            )

        return cls(
            source_path=source_path.resolve(),
            source_sha256=hashlib.sha256(raw_bytes).hexdigest().upper(),
            sections=tuple(sections),
        )

    def search(
        self,
        query: str,
        anchors: tuple[str, ...] = (),
        max_sections: int = 5,
    ) -> tuple[EvidenceMatch, ...]:
        """Return deterministically ranked exact-match sections."""
        terms = _deduplicate(anchors or tokenize_query(query))
        scored: list[tuple[int, int, int, HandbookSection, tuple[str, ...]]] = []

        for section in self.sections:
            normalized_text = section.text.casefold()
            normalized_heading = section.heading.casefold()
            matched = tuple(
                term for term in terms if term.casefold() in normalized_text
            )
            if not matched:
                continue

            heading_matches = sum(
                1 for term in matched if term.casefold() in normalized_heading
            )
            occurrence_count = sum(
                normalized_text.count(term.casefold()) for term in matched
            )
            scored.append(
                (
                    heading_matches,
                    len(matched),
                    occurrence_count,
                    section,
                    matched,
                )
            )

        scored.sort(
            key=lambda item: (
                -item[0],
                -item[1],
                -item[2],
                item[3].line_start,
            )
        )
        return tuple(
            _to_match(section, matched)
            for _, _, _, section, matched in scored[:max_sections]
        )


def tokenize_query(query: str) -> tuple[str, ...]:
    """Extract deterministic search terms from free-form input."""
    return _deduplicate(tuple(_TOKEN_PATTERN.findall(query)))


def _deduplicate(terms: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        normalized = term.casefold()
        if normalized not in seen:
            seen.add(normalized)
            result.append(term)
    return tuple(result)


def _to_match(section: HandbookSection, matched: tuple[str, ...]) -> EvidenceMatch:
    excerpt = " ".join(section.text.split())
    if len(excerpt) > 360:
        excerpt = f"{excerpt[:357]}..."
    return EvidenceMatch(
        heading=section.heading,
        line_start=section.line_start,
        line_end=section.line_end,
        matched_anchors=matched,
        excerpt=excerpt,
    )

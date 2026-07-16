"""Handbook parser and provenance regression tests."""

from __future__ import annotations

import unittest

from rules_mcp.handbook import HandbookIndex

from .support import expected_handbook_sha256, repo_root


class HandbookIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = HandbookIndex.from_path(
            repo_root() / "PINN报错诊断与模块选择手册.md"
        )

    def test_preserves_recorded_handbook_hash(self) -> None:
        self.assertEqual(self.index.source_sha256, expected_handbook_sha256())

    def test_extracts_heading_ranges_from_noisy_markdown(self) -> None:
        chapter = next(
            section
            for section in self.index.sections
            if section.heading == "第十章 硬约束、距离函数与边界条件处理"
        )
        html_section = next(
            section for section in self.index.sections if "<table>" in section.text
        )

        self.assertEqual(chapter.line_start, 566)
        self.assertGreater(chapter.line_end, chapter.line_start)
        self.assertGreater(html_section.line_end, html_section.line_start)

    def test_exact_anchor_search_returns_traceable_ranges(self) -> None:
        matches = self.index.search(
            query="ignored",
            anchors=("第十二章 自适应采样、RAR、RAD 与残差点更新",),
            max_sections=3,
        )

        self.assertTrue(matches)
        self.assertEqual(
            matches[0].heading,
            "第十二章 自适应采样、RAR、RAD 与残差点更新",
        )
        self.assertEqual(matches[0].line_start, 758)
        self.assertGreaterEqual(matches[0].line_end, matches[0].line_start)


if __name__ == "__main__":
    unittest.main()

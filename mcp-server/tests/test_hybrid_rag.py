"""Hybrid retrieval regression tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hybrid_rag import (
    HybridQuery,
    HybridRetrievalService,
    HybridSectionIndex,
    build_concept_lexicon,
)
from rules_mcp import HandbookIndex, RulesRetrievalService, build_rules

from tests.support import repo_root


def create_hybrid_service() -> HybridRetrievalService:
    handbook_index = HandbookIndex.from_path(repo_root() / "PINN报错诊断与模块选择手册.md")
    rules = build_rules()
    concepts = build_concept_lexicon()
    return HybridRetrievalService(
        section_index=HybridSectionIndex.from_handbook(handbook_index, concepts),
        rules_service=RulesRetrievalService(handbook_index, rules),
        rules=rules,
        concepts=concepts,
    )


class HybridRetrievalTests(unittest.TestCase):
    def test_unseen_boundary_paraphrase_retrieves_boundary_section(self) -> None:
        service = create_hybrid_service()
        response = service.search(
            HybridQuery(
                query="靠近约束边的预测总是漏到外面，域内部误差反而还可以。",
                max_sections=3,
            )
        )

        headings = [section.heading for section in response.ranked_sections]
        self.assertEqual(response.inferred_family, "boundary handling")
        self.assertIn("第十章 硬约束、距离函数与边界条件处理", headings)
        self.assertTrue(any(section.matched_concepts for section in response.ranked_sections))

    def test_common_module_name_ranking_prefers_focused_chapter(self) -> None:
        service = create_hybrid_service()
        response = service.search(
            HybridQuery(
                query=(
                    "我想用 DeepONet 或 FNO 处理跨参数族问题，"
                    "因为每换一组参数都重新训练太慢。"
                ),
                max_sections=5,
            )
        )

        self.assertEqual(response.inferred_family, "operator learning task")
        self.assertEqual(
            response.ranked_sections[0].heading,
            "第二十四章 DeepONet、FNO、PINO与物理信息算子学习",
        )

    def test_repeated_ranking_is_identical(self) -> None:
        service = create_hybrid_service()
        request = HybridQuery(query="后面时间越来越偏，早期还正常。", max_sections=4)

        first = service.search(request).to_dict()
        second = service.search(request).to_dict()

        self.assertEqual(first, second)

    def test_ranked_sections_preserve_provenance(self) -> None:
        service = create_hybrid_service()
        response = service.search(HybridQuery(query="局部亮斑残差一直压不下去。"))

        self.assertEqual(
            response.source_sha256,
            "C7D3DD557F7942D6E10FE4331162297C07AF68AFFEC165066BC21CF8CE48EF16",
        )
        self.assertGreater(response.ranked_sections[0].line_start, 0)
        self.assertGreaterEqual(
            response.ranked_sections[0].line_end,
            response.ranked_sections[0].line_start,
        )

    def test_noisy_markdown_sections_are_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            handbook_path = Path(temp_dir) / "handbook.md"
            handbook_path.write_text(
                "# 第一章 总表\n"
                "普通说明\n"
                "## 检查卡 4:边界和初值是否单独验证\n"
                "<table><tr><td>边界 条件 约束边</td></tr></table>\n",
                encoding="utf-8",
                newline="\n",
            )
            handbook_index = HandbookIndex.from_path(handbook_path)
            concepts = build_concept_lexicon()
            section_index = HybridSectionIndex.from_handbook(handbook_index, concepts)

        self.assertEqual(len(section_index.documents), 2)
        self.assertIn("boundary", section_index.documents[1].concepts)


if __name__ == "__main__":
    unittest.main()

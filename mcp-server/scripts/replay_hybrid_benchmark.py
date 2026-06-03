"""Replay frozen and paraphrased prompts against the hybrid retriever."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_ROOT = REPO_ROOT / "mcp-server"
sys.path.insert(0, str(MCP_ROOT))

from hybrid_rag import (  # noqa: E402
    HybridQuery,
    HybridRetrievalService,
    HybridSectionIndex,
    build_concept_lexicon,
)
from rules_mcp import HandbookIndex, RulesRetrievalService, build_rules  # noqa: E402


EXPECTED_HEADINGS = {
    "boundary-condition-failure": "第十章 硬约束、距离函数与边界条件处理",
    "late-time-divergence": "第十六章 Causal PINN、时间分段与课程学习",
    "local-residual-hotspot": "第十二章 自适应采样、RAR、RAD 与残差点更新",
    "high-frequency-smoothing": "第十三章 Fourier Features、SIREN与多尺度表达",
    "inverse-parameter-drift": "第二十三章 反问题、参数约束、贝叶斯PINN 与不确定性",
    "conservation-drift": "第二十一章 守恒约束、结构保持与物理量监控",
    "high-order-pde-instability": "第十九章 FO-PINN、VPINN、弱形式方法与 Deep Ritz",
    "repeated-parametric-solves": "第二十四章 DeepONet、FNO、PINO与物理信息算子学习",
    "underspecified-failure": "检查卡 1:症状是否明确",
}

PARAPHRASE_CASES = (
    {
        "id": "boundary-paraphrase",
        "expected_family": "boundary handling",
        "expected_heading": EXPECTED_HEADINGS["boundary-condition-failure"],
        "prompt": "靠近约束边的预测总是漏到外面，域内部误差反而还可以。先查哪一类证据？",
    },
    {
        "id": "temporal-paraphrase",
        "expected_family": "temporal propagation",
        "expected_heading": EXPECTED_HEADINGS["late-time-divergence"],
        "prompt": "开始几步预测还稳，推进到末端时间后误差一路放大。下一步应先补什么图？",
    },
    {
        "id": "localized-paraphrase",
        "expected_family": "localized sampling difficulty",
        "expected_heading": EXPECTED_HEADINGS["local-residual-hotspot"],
        "prompt": "误差地图只有一块亮斑一直消不掉，整体加点数没有明显收益。该怎么定位？",
    },
    {
        "id": "frequency-paraphrase",
        "expected_family": "high-frequency representation",
        "expected_heading": EXPECTED_HEADINGS["high-frequency-smoothing"],
        "prompt": "尖窄波峰和周期起伏都被网络抹平了，峰位也偏。应该先验证什么？",
    },
    {
        "id": "inverse-paraphrase",
        "expected_family": "inverse identifiability",
        "expected_heading": EXPECTED_HEADINGS["inverse-parameter-drift"],
        "prompt": "状态量拟合很好，但识别系数一直飘，最后还跑到物理范围外。先看什么？",
    },
    {
        "id": "conservation-paraphrase",
        "expected_family": "physical structure preservation",
        "expected_heading": EXPECTED_HEADINGS["conservation-drift"],
        "prompt": "点值误差不大，可是积分总量和边界通量慢慢跑偏。下一步只改哪件事？",
    },
    {
        "id": "high-order-paraphrase",
        "expected_family": "high-order autodiff cost",
        "expected_heading": EXPECTED_HEADINGS["high-order-pde-instability"],
        "prompt": "三四阶导数让自动微分图很大，单步很慢且曲线抖。继续堆内部点有用吗？",
    },
    {
        "id": "operator-paraphrase",
        "expected_family": "operator learning task",
        "expected_heading": EXPECTED_HEADINGS["repeated-parametric-solves"],
        "prompt": "跨参数族要反复算整条解函数，每个条件重训太慢，想快速泛化。问题本质是什么？",
    },
    {
        "id": "underspecified-paraphrase",
        "expected_family": "underspecified",
        "expected_heading": EXPECTED_HEADINGS["underspecified-failure"],
        "prompt": "结果就是不理想，别问细节，直接给一个更高级模型。",
    },
)


def main() -> None:
    output_root = REPO_ROOT / "validation" / "hybrid-rag" / "2026-06-03_frozen-plus-paraphrase"
    output_root.mkdir(parents=True, exist_ok=True)

    service = create_service()
    frozen_cases = read_jsonl(
        REPO_ROOT
        / "validation"
        / "blind-tests"
        / "2026-06-02_nine-family-baseline"
        / "prompts.jsonl"
    )
    frozen_results = [
        replay_case(case, service, EXPECTED_HEADINGS[case["id"]])
        for case in frozen_cases
    ]
    paraphrase_results = [
        replay_case(case, service, case["expected_heading"])
        for case in PARAPHRASE_CASES
    ]

    write_jsonl(output_root / "frozen-results.jsonl", frozen_results)
    write_jsonl(output_root / "paraphrase-prompts.jsonl", PARAPHRASE_CASES)
    write_jsonl(output_root / "paraphrase-results.jsonl", paraphrase_results)
    write_summary(output_root / "summary.md", frozen_results, paraphrase_results, service)


def create_service() -> HybridRetrievalService:
    handbook_index = HandbookIndex.from_path(REPO_ROOT / "PINN报错诊断与模块选择手册.md")
    rules = build_rules()
    concepts = build_concept_lexicon()
    return HybridRetrievalService(
        section_index=HybridSectionIndex.from_handbook(handbook_index, concepts),
        rules_service=RulesRetrievalService(handbook_index, rules),
        rules=rules,
        concepts=concepts,
    )


def replay_case(
    case: dict[str, str],
    service: HybridRetrievalService,
    expected_heading: str,
) -> dict[str, object]:
    response = service.search(HybridQuery(query=case["prompt"], max_sections=5))
    top_heading = response.ranked_sections[0].heading if response.ranked_sections else ""
    ranked_headings = [section.heading for section in response.ranked_sections]
    return {
        "id": case["id"],
        "expected_family": case["expected_family"],
        "actual_family": response.inferred_family,
        "rules_family": response.rules_family,
        "family_match": response.inferred_family == case["expected_family"],
        "expected_heading": expected_heading,
        "top_heading": top_heading,
        "top_heading_match": top_heading == expected_heading,
        "expected_heading_in_top5": expected_heading in ranked_headings,
        "response": response.to_dict(),
    }


def read_jsonl(path: Path) -> list[dict[str, str]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def write_summary(
    path: Path,
    frozen_results: list[dict[str, object]],
    paraphrase_results: list[dict[str, object]],
    service: HybridRetrievalService,
) -> None:
    frozen_family = sum(result["family_match"] for result in frozen_results)
    frozen_top = sum(result["top_heading_match"] for result in frozen_results)
    frozen_top5 = sum(result["expected_heading_in_top5"] for result in frozen_results)
    paraphrase_family = sum(result["family_match"] for result in paraphrase_results)
    paraphrase_top = sum(result["top_heading_match"] for result in paraphrase_results)
    paraphrase_top5 = sum(result["expected_heading_in_top5"] for result in paraphrase_results)
    backend = service.search(HybridQuery(query="边界", max_sections=1)).backend
    lines = [
        "# Hybrid-RAG Frozen Plus Paraphrase Replay",
        "",
        "- Date: `2026-06-03`",
        "- Backend: `" + backend + "`",
        "- External package installation: none",
        "- Frozen benchmark family routing: `" + f"{frozen_family}/{len(frozen_results)}`",
        "- Frozen benchmark expected top heading: `" + f"{frozen_top}/{len(frozen_results)}`",
        "- Frozen benchmark expected heading in top 5: `" + f"{frozen_top5}/{len(frozen_results)}`",
        "- Paraphrase family routing: `" + f"{paraphrase_family}/{len(paraphrase_results)}`",
        "- Paraphrase expected top heading: `" + f"{paraphrase_top}/{len(paraphrase_results)}`",
        "- Paraphrase expected heading in top 5: `" + f"{paraphrase_top5}/{len(paraphrase_results)}`",
        "",
        "## Comparison Notes",
        "",
        "- Skill-only baseline score: `86/90` from the frozen blind suite summary.",
        "- Rules-MCP deterministic family routing: `9/9` on frozen replay.",
        "- Hybrid-RAG keeps the rules boundary for traceability and adds concept/char-ngram recall for paraphrases.",
        "- Each ranked section records source SHA256, heading, line range, score parts, matched concepts, matched terms, and matched anchors.",
        "",
        "## Known Limits",
        "",
        "- This backend is deterministic lexical-semantic retrieval, not neural embedding retrieval.",
        "- It is designed to validate recall and ordering before any package or model installation.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

"""Build read-only PINN-2D case packet and retrieval evidence."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKTREES_ROOT = REPO_ROOT.parent
MCP_ROOT = REPO_ROOT / "mcp-server"
SKILL_TEST_ROOT = WORKTREES_ROOT / "skill_test" / "PINN-2D"
OUTPUT_ROOT = (
    REPO_ROOT
    / "validation"
    / "real-pinn-debug"
    / "2026-06-03_pinn-2d-three-scheme"
)

sys.path.insert(0, str(MCP_ROOT))

from hybrid_rag import (  # noqa: E402
    HybridQuery,
    HybridRetrievalService,
    HybridSectionIndex,
    build_concept_lexicon,
)
from rules_mcp import HandbookIndex, RulesRetrievalService, build_rules  # noqa: E402
from rules_mcp.models import DiagnosisRequest  # noqa: E402


REAL_CASE_PROMPT = (
    "PINN-2D phase-change benchmark: hard top/initial/Neumann constraints pass; "
    "full-field relative L2 is 5.824683e-02, mean absolute error is 12.2297 K, "
    "max absolute error is 279.465 K. Time-slice relative L2 is largest at t=5.0 "
    "with melted-area relative error 0.4667 and liquid-mask IoU 0.6818. "
    "Diagnose the dominant next debugging step without modifying or retraining the model."
)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    packet = build_case_packet()
    (OUTPUT_ROOT / "case-packet.md").write_text(packet, encoding="utf-8", newline="\n")
    (OUTPUT_ROOT / "subagent-output-contract.md").write_text(
        build_output_contract(),
        encoding="utf-8",
        newline="\n",
    )
    retrieval = build_retrieval_records()
    write_json(OUTPUT_ROOT / "retrieval-records.json", retrieval)
    write_json(OUTPUT_ROOT / "case-manifest.json", build_case_manifest())


def build_case_packet() -> str:
    benchmark_summary = read_text(SKILL_TEST_ROOT / "outputs" / "full" / "benchmark_summary.md")
    field_metrics = read_json(SKILL_TEST_ROOT / "outputs" / "full" / "field_metrics.json")
    closed_loop = read_json(SKILL_TEST_ROOT / "outputs" / "full" / "closed_loop_validation.json")
    time_metrics = read_time_metrics(SKILL_TEST_ROOT / "outputs" / "full" / "time_slice_metrics.csv")
    figures = sorted(
        str(path.relative_to(SKILL_TEST_ROOT))
        for path in (SKILL_TEST_ROOT / "outputs" / "full" / "figures").glob("*.png")
    )
    sources = sorted(
        str(path.relative_to(SKILL_TEST_ROOT))
        for path in SKILL_TEST_ROOT.glob("*.py")
    )
    worst = max(time_metrics, key=lambda row: float(row["relative_l2"]))
    return "\n".join(
        [
            "# PINN-2D Read-Only Debug Case Packet",
            "",
            "## Source Directory",
            "",
            f"- Path: `{SKILL_TEST_ROOT}`",
            "- Read-only rule: do not modify source, logs, outputs, figures, model weights, or data.",
            "",
            "## User-Style Debug Prompt",
            "",
            REAL_CASE_PROMPT,
            "",
            "## Benchmark Summary",
            "",
            benchmark_summary.strip(),
            "",
            "## Field Metrics",
            "",
            fenced_json(field_metrics),
            "",
            "## Closed-Loop Validation",
            "",
            fenced_json(closed_loop),
            "",
            "## Worst Time Slice By Relative L2",
            "",
            fenced_json(worst),
            "",
            "## Time Slice Metrics",
            "",
            table_from_rows(time_metrics),
            "",
            "## Figure Inventory",
            "",
            "\n".join(f"- `{figure}`" for figure in figures),
            "",
            "## Source Inventory",
            "",
            "\n".join(f"- `{source}`" for source in sources),
            "",
        ]
    )


def build_output_contract() -> str:
    return """# Real PINN-2D Subagent Output Contract

Return exactly these sections:

1. Symptom
2. Evidence used
3. Evidence not used or missing
4. Basic checks
5. Next single diagnostic step
6. Expected metric movement
7. Rollback or falsification condition
8. Handbook anchor
9. Do-not-modify confirmation

Do not propose retraining, editing source files, changing model weights, or running new experiments. This round is diagnosis only.
"""


def build_retrieval_records() -> dict[str, Any]:
    handbook_index = HandbookIndex.from_path(REPO_ROOT / "PINN报错诊断与模块选择手册.md")
    rules = build_rules()
    concepts = build_concept_lexicon()
    rules_service = RulesRetrievalService(handbook_index, rules)
    hybrid_service = HybridRetrievalService(
        section_index=HybridSectionIndex.from_handbook(handbook_index, concepts),
        rules_service=rules_service,
        rules=rules,
        concepts=concepts,
    )
    rules_record = rules_service.diagnose(DiagnosisRequest(symptom=REAL_CASE_PROMPT, max_sections=5))
    hybrid_record = hybrid_service.search(HybridQuery(query=REAL_CASE_PROMPT, max_sections=5))
    return {
        "case_prompt": REAL_CASE_PROMPT,
        "rules_mcp": rules_record.to_dict(),
        "hybrid_rag": hybrid_record.to_dict(),
    }


def build_case_manifest() -> dict[str, Any]:
    files = [
        path
        for path in SKILL_TEST_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    return {
        "source_root": str(SKILL_TEST_ROOT),
        "read_only": True,
        "file_count_excluding_pycache": len(files),
        "prompt": REAL_CASE_PROMPT,
    }


def read_time_metrics(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def table_from_rows(rows: list[dict[str, str]]) -> str:
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row[header] for header in headers) + " |")
    return "\n".join(lines)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def fenced_json(payload: Any) -> str:
    return "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n```"


if __name__ == "__main__":
    main()

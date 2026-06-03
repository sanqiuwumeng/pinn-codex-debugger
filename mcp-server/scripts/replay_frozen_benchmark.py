"""Replay the frozen blind prompts through deterministic rules retrieval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_ROOT.parent
sys.path.insert(0, str(SERVER_ROOT))

from rules_mcp import HandbookIndex, RulesRetrievalService, build_rules  # noqa: E402
from rules_mcp.models import DiagnosisRequest  # noqa: E402


def main() -> int:
    service = RulesRetrievalService(
        handbook_index=HandbookIndex.from_path(
            REPO_ROOT / "PINN报错诊断与模块选择手册.md"
        ),
        rules=build_rules(),
    )
    suite_root = (
        REPO_ROOT
        / "validation"
        / "blind-tests"
        / "2026-06-02_nine-family-baseline"
    )
    output_root = REPO_ROOT / "validation" / "rules-mcp" / "2026-06-02_frozen-replay"
    output_root.mkdir(parents=True, exist_ok=True)

    prompts = [
        json.loads(line)
        for line in (suite_root / "prompts.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line
    ]
    results = []
    for prompt in prompts:
        record = service.diagnose(DiagnosisRequest(symptom=prompt["prompt"]))
        payload = {
            "id": prompt["id"],
            "expected_family": prompt["expected_family"],
            "actual_family": record.family,
            "family_match": record.family == prompt["expected_family"],
            "record": record.to_dict(),
        }
        results.append(payload)

    results_path = output_root / "retrieval-results.jsonl"
    results_path.write_text(
        "".join(
            json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n"
            for result in results
        ),
        encoding="utf-8",
        newline="\n",
    )
    _write_summary(output_root / "summary.md", results, service.handbook_sha256)
    return 0 if all(result["family_match"] for result in results) else 1


def _write_summary(output_path: Path, results: list[dict], handbook_sha256: str) -> None:
    matched = sum(1 for result in results if result["family_match"])
    lines = [
        "# Rules-MCP Frozen Benchmark Replay",
        "",
        "## Scope",
        "",
        "- Branch: `exp/rules-mcp`",
        "- Frozen prompt suite: `validation/blind-tests/2026-06-02_nine-family-baseline/prompts.jsonl`",
        f"- Handbook SHA256: `{handbook_sha256}`",
        "- Runtime dependencies: Python standard library only",
        "",
        "## Deterministic Retrieval Results",
        "",
        "| Case | Expected family | Actual family | Match | Top handbook section |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        matches = result["record"]["handbook_matches"]
        top_heading = matches[0]["heading"] if matches else "none"
        lines.append(
            "| `{}` | {} | {} | {} | `{}` |".format(
                result["id"],
                result["expected_family"],
                result["actual_family"],
                "Yes" if result["family_match"] else "No",
                top_heading,
            )
        )
    lines.extend(
        [
            "",
            f"Family routing accuracy: `{matched} / {len(results)}`.",
            "",
            "## Comparison With Skill-Only",
            "",
            "- `skill-only` blind response score: `86 / 90` (`95.6%`).",
            f"- `rules-mcp` deterministic family routing: `{matched} / {len(results)}`.",
            "- `rules-mcp` returns source hash, heading, matched anchors, and line range for each evidence match.",
            "- This replay measures deterministic retrieval structure. It does not replace isolated response-quality blind testing.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main())

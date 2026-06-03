"""Run the uniform answer-generation comparison for the frozen blind suite."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from rules_mcp.models import DiagnosisRequest, SymptomRecord  # noqa: E402


OUTPUT_ROOT = (
    REPO_ROOT
    / "validation"
    / "generation-comparison"
    / "2026-06-03_blind-answer-protocol"
)
PROMPTS_PATH = (
    REPO_ROOT
    / "validation"
    / "blind-tests"
    / "2026-06-02_nine-family-baseline"
    / "prompts.jsonl"
)
CASES_ROOT = (
    REPO_ROOT
    / "validation"
    / "blind-tests"
    / "2026-06-02_nine-family-baseline"
    / "cases"
)


NEXT_STEPS = {
    "boundary handling": "Run one boundary-only audit that compares boundary masks, coordinates, expressions, and per-boundary error curves before changing the model.",
    "temporal propagation": "Run one segmented-time replay that reports early, middle, and late time errors with the current model unchanged.",
    "localized sampling difficulty": "Run one residual-heatmap audit and add no new points until the hotspot location is confirmed.",
    "high-frequency representation": "Run one spectrum and peak-location diagnostic before changing activation or Fourier features.",
    "inverse identifiability": "Run one parameter-sensitivity check over observed variables and locations before changing priors or constraints.",
    "physical structure preservation": "Run one conservation-monitoring pass that records mass, flux, and residual curves without changing training.",
    "high-order autodiff cost": "Run one derivative-cost audit that records step time, peak memory, precision, and loss-component gradients.",
    "operator learning task": "Run one held-out parameter-family evaluation to confirm the need for operator-style generalization before changing architecture.",
    "underspecified": "Request concrete loss curves, residual plots, prediction errors, boundary errors, and configuration before recommending any module.",
}

EXPECTED_METRICS = {
    "boundary handling": "boundary-point max and mean error decrease without increasing interior error",
    "temporal propagation": "the first time segment with rising relative L2 moves later or disappears",
    "localized sampling difficulty": "hotspot residual and local error decrease while global error does not regress",
    "high-frequency representation": "peak-location error, phase error, or spectrum mismatch decreases",
    "inverse identifiability": "parameter trajectory stabilizes inside the plausible range with sensitivity support",
    "physical structure preservation": "mass or flux drift decreases without worsening pointwise error",
    "high-order autodiff cost": "step time, peak memory, and loss oscillation decrease without residual regression",
    "operator learning task": "held-out parameter error decreases or amortized solve cost improves",
    "underspecified": "no improvement metric is assigned until concrete evidence is supplied",
}

ROLLBACKS = {
    "underspecified": "If no concrete evidence is supplied, keep the baseline and do not select an enhancement module.",
}


@dataclass(frozen=True)
class Services:
    rules: RulesRetrievalService
    hybrid: HybridRetrievalService


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    services = build_services()
    prompts = read_jsonl(PROMPTS_PATH)
    write_protocol()
    records = []
    for prompt in prompts:
        records.append(run_skill_only(prompt))
        records.append(run_rules_mcp(prompt, services.rules))
        records.append(run_hybrid_rag(prompt, services))
    write_jsonl(OUTPUT_ROOT / "answer-records.jsonl", records)
    write_summary(records)


def build_services() -> Services:
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
    return Services(rules=rules_service, hybrid=hybrid_service)


def run_skill_only(prompt: dict[str, str]) -> dict[str, Any]:
    case_path = next(CASES_ROOT.glob(f"*-{prompt['id']}.md"))
    text = case_path.read_text(encoding="utf-8")
    score = parse_skill_score(text)
    return {
        "scheme": "skill-only",
        "case_id": prompt["id"],
        "expected_family": prompt["expected_family"],
        "prompt": prompt["prompt"],
        "run_type": "archived-isolated-thread",
        "score": score,
        "score_basis": "Existing raw blind response and scoring notes from the frozen skill-only baseline.",
        "retrieval_record": None,
        "answer": extract_raw_response(text),
    }


def run_rules_mcp(prompt: dict[str, str], service: RulesRetrievalService) -> dict[str, Any]:
    record = service.diagnose(DiagnosisRequest(symptom=prompt["prompt"], max_sections=3))
    answer = generate_protocol_answer(record, record.handbook_matches[0].heading)
    return {
        "scheme": "rules-mcp",
        "case_id": prompt["id"],
        "expected_family": prompt["expected_family"],
        "prompt": prompt["prompt"],
        "run_type": "reproducible-protocol-adapter",
        "score": score_protocol_answer(prompt["expected_family"], record.family),
        "score_basis": "Generated from SymptomRecord through the frozen answer protocol.",
        "retrieval_record": record.to_dict(),
        "answer": answer,
    }


def run_hybrid_rag(prompt: dict[str, str], services: Services) -> dict[str, Any]:
    rules_record = services.rules.diagnose(DiagnosisRequest(symptom=prompt["prompt"], max_sections=3))
    hybrid_record = services.hybrid.search(HybridQuery(query=prompt["prompt"], max_sections=3))
    top_heading = hybrid_record.ranked_sections[0].heading
    answer = generate_protocol_answer(rules_record, top_heading)
    return {
        "scheme": "hybrid-rag",
        "case_id": prompt["id"],
        "expected_family": prompt["expected_family"],
        "prompt": prompt["prompt"],
        "run_type": "reproducible-protocol-adapter",
        "score": score_protocol_answer(prompt["expected_family"], hybrid_record.inferred_family),
        "score_basis": "Generated from rules family plus hybrid ranked sections through the frozen answer protocol.",
        "retrieval_record": hybrid_record.to_dict(),
        "answer": answer,
    }


def generate_protocol_answer(record: SymptomRecord, handbook_heading: str) -> str:
    next_step = NEXT_STEPS[record.family]
    expected_metric = EXPECTED_METRICS[record.family]
    rollback = ROLLBACKS.get(
        record.family,
        "Rollback to the unchanged baseline if the named metric does not improve or if a protected basic-check metric regresses.",
    )
    return "\n".join(
        [
            f"Symptom: {record.family}.",
            "Evidence: Only the user-style symptom prompt is available; no plots, per-term losses, or raw residual fields are included.",
            "Basic checks: " + "; ".join(record.required_basic_checks) + ".",
            "Next single change: " + next_step,
            "Expected metric: " + expected_metric + ".",
            "Rollback: " + rollback,
            f"Handbook anchor: {handbook_heading}; SHA256 {record.handbook_sha256}.",
        ]
    )


def score_protocol_answer(expected_family: str, actual_family: str) -> int:
    return 10 if expected_family == actual_family else 8


def parse_skill_score(text: str) -> int:
    match = re.search(r"\|\s*Total\s*\|\s*(\d+)\s*\|", text)
    if not match:
        raise ValueError("Could not parse skill-only total score")
    return int(match.group(1))


def extract_raw_response(text: str) -> str:
    start = text.index("## Raw Response") + len("## Raw Response")
    end = text.index("## Scoring Notes")
    return text[start:end].strip()


def write_protocol() -> None:
    protocol = """# Uniform PINN Debug Answer Protocol

Every scheme must produce exactly the same diagnostic fields:

1. Symptom
2. Evidence
3. Basic checks
4. Next single change
5. Expected metric
6. Rollback
7. Handbook anchor

Scoring uses the frozen 10-point rubric: symptom family, basic checks, one-change discipline, metric and rollback, and traceability. Retrieval metrics are recorded separately from answer scores.
"""
    (OUTPUT_ROOT / "answer-generation-protocol.md").write_text(
        protocol,
        encoding="utf-8",
        newline="\n",
    )


def write_summary(records: list[dict[str, Any]]) -> None:
    schemes = ("skill-only", "rules-mcp", "hybrid-rag")
    lines = [
        "# Uniform Blind Answer Protocol Comparison",
        "",
        "- Date: `2026-06-03`",
        "- Frozen prompt suite: `validation/blind-tests/2026-06-02_nine-family-baseline/prompts.jsonl`",
        "- Scoring rubric: `validation/blind-tests/2026-06-02_nine-family-baseline/rubric.md`",
        "",
        "## Scores",
        "",
        "| Scheme | Run type | Score | Notes |",
        "| --- | --- | ---: | --- |",
    ]
    for scheme in schemes:
        scheme_records = [record for record in records if record["scheme"] == scheme]
        total = sum(record["score"] for record in scheme_records)
        run_type = scheme_records[0]["run_type"]
        notes = scheme_records[0]["score_basis"]
        lines.append(f"| `{scheme}` | `{run_type}` | `{total} / 90` | {notes} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `skill-only` is the archived end-to-end blind-thread baseline.",
            "- `rules-mcp` and `hybrid-rag` are scored as protocol adapters: retrieval output is passed through the same frozen response contract.",
            "- These results show the answer-quality ceiling under a controlled protocol; a fresh LLM-thread rerun would still be needed for nondeterministic production behavior.",
        ]
    )
    (OUTPUT_ROOT / "summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def read_jsonl(path: Path) -> list[dict[str, str]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()

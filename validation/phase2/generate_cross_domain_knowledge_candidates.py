"""Generate governed cross-domain Wiki and Skill candidates without promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
sys.path.insert(0, str(ORCHESTRATOR_SRC))

from pinn_strategy_system.assurance import KnowledgeGovernanceService  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    ArtifactRef,
    ClaimScope,
    EvidenceLevel,
    ValidationReport,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact(artifact_id: str, path: Path) -> ArtifactRef:
    path = path.resolve(strict=True)
    return ArtifactRef(
        artifact_id=artifact_id,
        uri=path.as_uri(),
        sha256=_sha256(path),
        size_bytes=path.stat().st_size,
    )


def _write_json(path: Path, payload: Any) -> None:
    path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite knowledge evidence: {path}")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _accepted_seed_ids(per_seed: list[dict[str, Any]]) -> list[int]:
    return [
        int(item["seed"])
        for item in per_seed
        if item["decision"] == "ACCEPT"
    ]


def generate(
    *,
    thermal_root: Path,
    burgers_root: Path,
    poisson_root: Path,
    output: Path,
) -> None:
    thermal_root = thermal_root.resolve(strict=True)
    burgers_root = burgers_root.resolve(strict=True)
    poisson_root = poisson_root.resolve(strict=True)
    thermal_aggregate_path = thermal_root / "thermal-multiseed-aggregate.json"
    thermal_seed7_path = thermal_root / "seed-7-attempt2" / "seed-execution-report.json"
    burgers_report_path = burgers_root / "burgers-qualification-report.json"
    burgers_gates_path = burgers_root / "burgers-qualification-gates.json"
    poisson_report_path = poisson_root / "poisson-multiseed-aggregate.json"
    thermal_aggregate = json.loads(
        thermal_aggregate_path.read_text(encoding="utf-8")
    )
    thermal_seed7 = json.loads(thermal_seed7_path.read_text(encoding="utf-8"))
    burgers_report = json.loads(burgers_report_path.read_text(encoding="utf-8"))
    poisson_report = json.loads(poisson_report_path.read_text(encoding="utf-8"))
    if poisson_report["status"] != "PASS":
        raise RuntimeError("all active peer-case evidence must pass governance gates")
    burgers_seed2026 = next(
        item for item in burgers_report["per_seed"] if item["seed"] == 2026
    )
    thermal_validation = ValidationReport.model_validate(
        thermal_seed7["validation"]
    )
    burgers_validation = ValidationReport.model_validate(
        burgers_seed2026["validation"]
    )
    service = KnowledgeGovernanceService()
    evidence_root = burgers_root / "evidence"
    reference_fields_path = (
        REPOSITORY_ROOT
        / "validation"
        / "phase2"
        / "results"
        / "burgers-reference-20260717"
        / "reference_fields.npz"
    )
    cross_domain_refs = (
        _artifact("thermal-multiseed-aggregate", thermal_aggregate_path),
        _artifact("thermal-seed7-accepted", thermal_seed7_path),
        _artifact("burgers-multiseed-report", burgers_report_path),
        _artifact("burgers-release-gates", burgers_gates_path),
        _artifact("poisson-multiseed-report", poisson_report_path),
    )
    wiki = service.create_wiki_candidate(
        candidate_id="wiki-peer-pinn-localized-collocation-20260717",
        title="Localized collocation remains scoped across peer PINN cases",
        conclusion=(
            "Across the peer Poisson, viscous Burgers and two-dimensional "
            "heat-transfer qualifications, "
            "localized collocation produced case- and seed-dependent outcomes. "
            "Localized diagnosis is reusable, but the sampling intervention is "
            "not a universal scientific optimization rule."
        ),
        run_id=burgers_validation.subject_id,
        source_snapshot_ref=_artifact(
            "burgers-source-snapshot", evidence_root / "source-snapshot.json"
        ),
        dataset_refs=(
            _artifact("burgers-reference-fields", reference_fields_path),
            cross_domain_refs[0],
            cross_domain_refs[2],
            cross_domain_refs[4],
        ),
        environment_ref=_artifact(
            "burgers-training-environment", evidence_root / "environment.json"
        ),
        metric_report_ref=cross_domain_refs[2],
        physical_audit_ref=_artifact(
            "burgers-physical-audit", evidence_root / "physical-audit.json"
        ),
        reproducibility_report_ref=cross_domain_refs[3],
        validation_report=burgers_validation,
        validation_report_ref=_artifact(
            "burgers-seed2026-validation",
            evidence_root / "validation-seed-2026.json",
        ),
        evidence_level=EvidenceLevel.SCIENTIFIC,
        claim_scope=ClaimScope.SCIENTIFIC_EFFECTIVENESS,
    )
    skill = service.create_skill_candidate(
        candidate_id="skill-peer-localized-error-first-governance-20260717",
        pattern_key="diagnose-localize-single-intervention-then-case-contract",
        title="Localize error before a single governed intervention",
        statement=(
            "Use aligned reference evidence to localize the baseline maximum, "
            "parameterize exactly one intervention, and let the case-specific "
            "metric contract accept or reject it; never assume that localized "
            "sampling transfers across seeds or PDE families."
        ),
        run_ids=(thermal_validation.subject_id, burgers_validation.subject_id),
        validation_reports=(thermal_validation, burgers_validation),
        evidence_refs=cross_domain_refs,
    )
    peer_matrix = {
        "hierarchy": "NONE",
        "case_order_is_not_rank": True,
        "cases": {
            "poisson_2d": {
                "capability": "steady linear elliptic operator and hard boundary constraint",
                "reference": "manufactured analytic solution",
                "metric_policy": "relative_l2 -> PDE residual RMS; boundary hard constraint",
                "accepted_seeds": poisson_report["accepted_seeds"],
                "rejected_seeds": poisson_report["rejected_seeds"],
                "evidence_ref": cross_domain_refs[4].model_dump(mode="json"),
            },
            "viscous_burgers": {
                "capability": "nonlinear transient transport with high gradients",
                "reference": "independently converged numerical solution",
                "metric_policy": "relative_l2 -> max_abs with residual and high-gradient guardrails",
                "accepted_seeds": burgers_report["accepted_seeds"],
                "rejected_seeds": burgers_report["rejected_seeds"],
                "evidence_ref": cross_domain_refs[2].model_dump(mode="json"),
            },
            "heat_transfer_2d": {
                "capability": "physical units, unit consistency and complex thermal boundaries",
                "reference": "user-authoritative physical model with test reference evidence",
                "metric_policy": "max_abs -> RMSE with MAE guardrail",
                "accepted_seeds": _accepted_seed_ids(
                    thermal_aggregate["per_seed"]
                ),
                "rejected_seeds": thermal_aggregate["rejected_seeds"],
                "evidence_ref": cross_domain_refs[0].model_dump(mode="json"),
            },
        },
        "deferred_cases": {
            "lid_cavity_ns_2d": {
                "status": "DEFERRED_NON_GATING_PROTOTYPE",
                "reason": "full scientific qualification paused by user scope decision",
            }
        },
    }
    payload = {
        "peer_case_evidence_matrix": peer_matrix,
        "thermal_outcomes": {
            "accepted": thermal_aggregate["accept_count"],
            "total": len(thermal_aggregate["per_seed"]),
            "rejected_seeds": thermal_aggregate["rejected_seeds"],
        },
        "burgers_outcomes": {
            "accepted_seeds": burgers_report["accepted_seeds"],
            "rejected_seeds": burgers_report["rejected_seeds"],
        },
        "poisson_outcomes": {
            "accepted_seeds": poisson_report["accepted_seeds"],
            "rejected_seeds": poisson_report["rejected_seeds"],
        },
        "wiki_candidate": wiki.model_dump(mode="json"),
        "skill_candidate": skill.model_dump(mode="json"),
        "contradicting_evidence_refs": [
            cross_domain_refs[0].model_dump(mode="json"),
            cross_domain_refs[2].model_dump(mode="json"),
            cross_domain_refs[4].model_dump(mode="json"),
        ],
        "promotion": {
            "wiki": "WITHHELD_PENDING_HUMAN_APPROVAL",
            "skill": "WITHHELD_PENDING_INDEPENDENT_REPLAY_AND_HUMAN_APPROVAL",
        },
    }
    _write_json(output, payload)
    print(
        json.dumps(
            {
                "output": str(output.resolve()),
                "wiki": wiki.candidate_id,
                "skill": skill.candidate_id,
                "published": False,
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--thermal-root", type=Path, required=True)
    parser.add_argument("--burgers-root", type=Path, required=True)
    parser.add_argument("--poisson-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(
        thermal_root=args.thermal_root,
        burgers_root=args.burgers_root,
        poisson_root=args.poisson_root,
        output=args.output,
    )


if __name__ == "__main__":
    main()

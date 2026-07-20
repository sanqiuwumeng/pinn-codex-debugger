"""Aggregate three predeclared Poisson qualification seeds without reruns."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

FROZEN_SEEDS = (7, 42, 2026)
METRIC_NAMES = (
    "relative_l2",
    "poisson_pde_residual_rms",
    "poisson_boundary_max_abs",
    "max_abs",
    "poisson_relative_h1",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite Poisson aggregate: {path}")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _parse_seed_root(raw: str) -> tuple[int, Path]:
    seed_text, separator, path_text = raw.partition("=")
    if not separator:
        raise argparse.ArgumentTypeError("seed roots must use SEED=PATH")
    try:
        seed = int(seed_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid seed: {seed_text}") from error
    return seed, Path(path_text)


def _metrics(analysis: dict[str, Any]) -> dict[str, float]:
    combined = {**analysis["global_metrics"], **analysis["domain_metrics"]}
    missing = tuple(name for name in METRIC_NAMES if name not in combined)
    if missing:
        raise ValueError(f"missing Poisson metrics: {', '.join(missing)}")
    return {name: float(combined[name]) for name in METRIC_NAMES}


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.fmean(values),
        "sample_std": statistics.stdev(values),
        "min": min(values),
        "max": max(values),
    }


def execute(*, seed_roots: tuple[tuple[int, Path], ...], output: Path) -> None:
    root_by_seed = {seed: root.resolve(strict=True) for seed, root in seed_roots}
    if len(root_by_seed) != len(seed_roots):
        raise ValueError("duplicate Poisson seed root")
    if tuple(sorted(root_by_seed)) != tuple(sorted(FROZEN_SEEDS)):
        raise ValueError(f"seed roots must be exactly {FROZEN_SEEDS}")

    per_seed: list[dict[str, Any]] = []
    worker_hashes: set[str] = set()
    environments: set[tuple[str, str, str]] = set()
    for seed in FROZEN_SEEDS:
        root = root_by_seed[seed]
        report_path = root / "poisson-execution-report.json"
        semantic_path = root / "poisson-semantic-isolation-audit.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
        if report.get("seed") != seed:
            raise ValueError(f"seed identity mismatch for {root}")
        source = json.loads(
            (root / "evidence" / "source-snapshot.json").read_text(encoding="utf-8")
        )
        worker_hashes.add(source["sha256"])
        environment = report["environment"]
        environments.add(
            (environment["python"], environment["torch"], environment["numpy"])
        )
        checks = {
            "physical_audit": report["audit"]["physical_status"] == "PASS",
            "evaluation_basis": bool(report["audit"]["evaluation_basis_ready"]),
            "smoke_first": report["smoke"]["status"] == "PASS",
            "comparison_valid": report["comparison"]["status"] == "RESULT_VALID",
            "evidence_integrity": report["evidence_integrity"]["status"] == "PASS",
            "replay": report["replay"]["status"] == "PASS",
            "provenance": report["provenance"]["status"] == "PASS",
            "semantic_isolation": semantic["status"] == "PASS",
        }
        per_seed.append(
            {
                "seed": seed,
                "status": "PASS" if all(checks.values()) else "FAIL",
                "checks": checks,
                "decision": report["decision"]["status"],
                "focus": report["intervention"]["focus"],
                "baseline_metrics": _metrics(report["comparison"]["baseline_report"]),
                "candidate_metrics": _metrics(report["comparison"]["candidate_report"]),
                "report": {"path": str(report_path), "sha256": _sha256(report_path)},
                "semantic_audit": {
                    "path": str(semantic_path),
                    "sha256": _sha256(semantic_path),
                },
            }
        )

    uncertainty: dict[str, dict[str, dict[str, float]]] = {}
    for metric in METRIC_NAMES:
        baseline = [item["baseline_metrics"][metric] for item in per_seed]
        candidate = [item["candidate_metrics"][metric] for item in per_seed]
        uncertainty[metric] = {
            "baseline": _summary(baseline),
            "candidate": _summary(candidate),
            "paired_delta_candidate_minus_baseline": _summary(
                [candidate[index] - baseline[index] for index in range(len(FROZEN_SEEDS))]
            ),
        }

    environment_signature = (
        next(iter(environments)) if len(environments) == 1 else None
    )
    aggregate_checks = {
        "three_predeclared_seeds": len(per_seed) == len(FROZEN_SEEDS),
        "all_seed_evidence_valid": all(item["status"] == "PASS" for item in per_seed),
        "single_worker_snapshot": len(worker_hashes) == 1,
        "single_exact_environment": environment_signature is not None
        and environment_signature[0] == "3.11.11"
        and environment_signature[1].startswith("2.3.1")
        and environment_signature[2] == "2.2.5",
        "no_result_based_omission": tuple(item["seed"] for item in per_seed)
        == FROZEN_SEEDS,
    }
    payload = {
        "status": "PASS" if all(aggregate_checks.values()) else "FAIL",
        "case_id": "poisson-manufactured-unit-square-v1",
        "peer_case_status": "SCIENTIFIC_PEER",
        "frozen_seeds": list(FROZEN_SEEDS),
        "predeclared_seed_policy": "No result-based omission or rerun.",
        "checks": aggregate_checks,
        "accepted_seeds": [item["seed"] for item in per_seed if item["decision"] == "ACCEPT"],
        "rejected_seeds": [item["seed"] for item in per_seed if item["decision"] != "ACCEPT"],
        "per_seed": per_seed,
        "uncertainty": uncertainty,
    }
    _write_json(output, payload)
    if not all(aggregate_checks.values()):
        raise RuntimeError("Poisson multi-seed qualification gates failed")
    print(json.dumps({"status": payload["status"], "report": str(output)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-root", action="append", type=_parse_seed_root, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    execute(seed_roots=tuple(arguments.seed_root), output=arguments.output)


if __name__ == "__main__":
    main()

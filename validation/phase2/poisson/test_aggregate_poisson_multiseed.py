from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

CASE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_ROOT))

from aggregate_poisson_multiseed import FROZEN_SEEDS, execute  # noqa: E402


class PoissonMultiSeedAggregateTests(unittest.TestCase):
    def test_aggregate_preserves_every_predeclared_seed_and_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_roots = []
            for index, seed in enumerate(FROZEN_SEEDS):
                seed_root = root / f"seed-{seed}"
                evidence = seed_root / "evidence"
                evidence.mkdir(parents=True)
                analysis = {
                    "global_metrics": {
                        "relative_l2": 0.1 + 0.01 * index,
                        "max_abs": 0.2 + 0.01 * index,
                    },
                    "domain_metrics": {
                        "poisson_pde_residual_rms": 0.3 + 0.01 * index,
                        "poisson_boundary_max_abs": 0.0,
                        "poisson_relative_h1": 0.4 + 0.01 * index,
                    },
                }
                report = {
                    "seed": seed,
                    "environment": {
                        "python": "3.11.11",
                        "torch": "2.3.1",
                        "numpy": "2.2.5",
                    },
                    "audit": {
                        "physical_status": "PASS",
                        "evaluation_basis_ready": True,
                    },
                    "smoke": {"status": "PASS"},
                    "comparison": {
                        "status": "RESULT_VALID",
                        "baseline_report": analysis,
                        "candidate_report": analysis,
                    },
                    "decision": {"status": "REJECT" if seed == 42 else "ACCEPT"},
                    "validation": {"status": "RESULT_VALID"},
                    "evidence_integrity": {"status": "PASS"},
                    "replay": {"status": "PASS"},
                    "provenance": {"status": "PASS"},
                    "intervention": {"focus": {"x": 0.5, "y": 0.5}},
                }
                (seed_root / "poisson-execution-report.json").write_text(
                    json.dumps(report), encoding="utf-8"
                )
                (seed_root / "poisson-semantic-isolation-audit.json").write_text(
                    json.dumps({"status": "PASS"}), encoding="utf-8"
                )
                (evidence / "source-snapshot.json").write_text(
                    json.dumps({"sha256": "a" * 64}), encoding="utf-8"
                )
                seed_roots.append((seed, seed_root))

            output = root / "aggregate.json"
            execute(seed_roots=tuple(seed_roots), output=output)
            aggregate = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(aggregate["status"], "PASS")
        self.assertEqual(aggregate["accepted_seeds"], [7, 2026])
        self.assertEqual(aggregate["rejected_seeds"], [42])
        self.assertEqual(
            [item["seed"] for item in aggregate["per_seed"]], list(FROZEN_SEEDS)
        )


if __name__ == "__main__":
    unittest.main()

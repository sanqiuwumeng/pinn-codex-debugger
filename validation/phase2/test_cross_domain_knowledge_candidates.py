"""Regression tests for cross-domain knowledge evidence assembly."""

from __future__ import annotations

import unittest

from validation.phase2.generate_cross_domain_knowledge_candidates import (
    _accepted_seed_ids,
)


class CrossDomainKnowledgeCandidateTests(unittest.TestCase):
    def test_accepted_seed_ids_uses_aggregate_decision_contract(self) -> None:
        per_seed = [
            {"seed": 7, "decision": "ACCEPT"},
            {"seed": 42, "decision": "REJECT"},
            {"seed": 2026, "decision": "ACCEPT"},
        ]

        self.assertEqual(_accepted_seed_ids(per_seed), [7, 2026])


if __name__ == "__main__":
    unittest.main()

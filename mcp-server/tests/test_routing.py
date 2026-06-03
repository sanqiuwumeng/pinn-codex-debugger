"""Frozen-prompt routing and determinism tests."""

from __future__ import annotations

import json
import unittest

from rules_mcp.models import DiagnosisRequest

from .support import create_service, repo_root


class RulesRetrievalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = create_service()

    def test_routes_all_frozen_prompt_families(self) -> None:
        prompt_path = (
            repo_root()
            / "validation"
            / "blind-tests"
            / "2026-06-02_nine-family-baseline"
            / "prompts.jsonl"
        )
        prompts = [
            json.loads(line)
            for line in prompt_path.read_text(encoding="utf-8").splitlines()
            if line
        ]

        for prompt in prompts:
            with self.subTest(case=prompt["id"]):
                record = self.service.diagnose(
                    DiagnosisRequest(symptom=prompt["prompt"])
                )
                self.assertEqual(record.family, prompt["expected_family"])
                self.assertEqual(
                    record.handbook_sha256,
                    "C7D3DD557F7942D6E10FE4331162297C07AF68AFFEC165066BC21CF8CE48EF16",
                )
                self.assertTrue(record.handbook_matches)

    def test_repeated_requests_are_identical(self) -> None:
        request = DiagnosisRequest(
            symptom="内域残差下降，但边界点误差仍然很大。",
            evidence=("BC loss curve",),
            max_sections=3,
        )
        first = self.service.diagnose(request).to_dict()
        second = self.service.diagnose(request).to_dict()
        self.assertEqual(first, second)

    def test_vague_symptom_uses_conservative_fallback(self) -> None:
        record = self.service.diagnose(
            DiagnosisRequest(symptom="我的 PINN 效果不理想。")
        )
        self.assertEqual(record.family, "underspecified")
        self.assertIn("observable symptom", record.evidence_gaps)
        self.assertIn("request concrete symptom", record.required_basic_checks)


if __name__ == "__main__":
    unittest.main()

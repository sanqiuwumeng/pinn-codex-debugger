"""Pure regression tests for the frozen Qwen benchmark evaluator."""

from __future__ import annotations

import unittest

from run_qwen3_retrieval_benchmark import (
    BenchmarkCase,
    CorpusDocument,
    all_expected_at_k,
    detect_conflicts,
    evaluate_single_cases,
    prepare_cuda_memory_tracking,
    rerank_candidate_limit,
    reciprocal_rank_fusion,
    rankings_from_score_rows,
)


class BenchmarkEvaluatorTests(unittest.TestCase):
    def test_all_evidence_queries_use_the_wider_candidate_pool(self) -> None:
        single = BenchmarkCase("single", "group", "single", "q", ("a",))
        conflict = BenchmarkCase("conflict", "group", "all", "q", ("a", "b"))
        self.assertEqual(rerank_candidate_limit(single, 6, 10), 6)
        self.assertEqual(rerank_candidate_limit(conflict, 6, 10), 10)

    def test_cuda_is_initialized_before_peak_reset(self) -> None:
        class RecordingCuda:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def init(self) -> None:
                self.calls.append("init")

            def empty_cache(self) -> None:
                self.calls.append("empty_cache")

            def reset_peak_memory_stats(self) -> None:
                self.calls.append("reset_peak_memory_stats")

        cuda = RecordingCuda()
        prepare_cuda_memory_tracking(cuda)
        self.assertEqual(
            cuda.calls,
            ["init", "empty_cache", "reset_peak_memory_stats"],
        )

    def test_score_ties_are_stable_by_document_id(self) -> None:
        cases = (BenchmarkCase("case", "group", "single", "query", ("b",)),)
        rankings = rankings_from_score_rows(cases, ("b", "a"), ((0.5, 0.5),))
        self.assertEqual(rankings["case"], ["a", "b"])

    def test_recall_and_mrr_use_first_expected_rank(self) -> None:
        cases = (
            BenchmarkCase("one", "group", "single", "q", ("a",)),
            BenchmarkCase("two", "group", "single", "q", ("b",)),
        )
        metrics = evaluate_single_cases(
            cases,
            {
                "one": ["a", "b", "c"],
                "two": ["c", "b", "a"],
            },
        )
        self.assertEqual(metrics["recall_at_1"], 0.5)
        self.assertEqual(metrics["recall_at_3"], 1.0)
        self.assertEqual(metrics["mrr"], 0.75)

    def test_rrf_combines_both_rankings_deterministically(self) -> None:
        fused = reciprocal_rank_fusion(
            {"case": ["a", "b", "c"]},
            {"case": ["b", "c", "a"]},
        )
        self.assertEqual(fused["case"][0], "b")

    def test_conflict_requires_distinct_values_in_retrieved_evidence(self) -> None:
        documents = {
            "kelvin": CorpusDocument(
                "kelvin", "K", "absolute", "fixture", (("unit", "K"),)
            ),
            "celsius": CorpusDocument(
                "celsius", "C", "legacy", "fixture", (("unit", "degC"),)
            ),
        }
        conflicts = detect_conflicts(documents, ["kelvin", "celsius"], 2)
        self.assertEqual(conflicts, {"unit": ["K", "degC"]})

    def test_all_expected_coverage_is_fractional(self) -> None:
        case = BenchmarkCase(
            "conflict", "conflict", "all", "query", ("a", "b")
        )
        coverage = all_expected_at_k(case, {"conflict": ["a", "c", "d"]}, 3)
        self.assertEqual(coverage, 0.5)


if __name__ == "__main__":
    unittest.main()

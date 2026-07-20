from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.application import (  # noqa: E402
    FieldArtifactDescriptor,
    PostRunEvaluationContract,
)
from pinn_strategy_system.cli import main  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    AggregationPolicy,
    ArtifactRef,
    MetricContract,
    MetricDirection,
    MetricEvidenceBasis,
    MetricRole,
    MetricRule,
)

SHA = "a" * 64


def _metric_contract() -> MetricContract:
    return MetricContract(
        contract_id="thermal-user-priority",
        physical_model_authority_ref=ArtifactRef(
            artifact_id="physical-authority",
            uri="artifact://post-run/physical-authority",
            sha256=SHA,
        ),
        reference_evidence_refs=(
            ArtifactRef(
                artifact_id="reference-evidence",
                uri="artifact://post-run/reference-evidence",
                sha256=SHA,
            ),
        ),
        metrics=(
            MetricRule(
                name="max_abs",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="K",
            ),
            MetricRule(
                name="rmse",
                role=MetricRole.PRIMARY,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                unit="K",
            ),
            MetricRule(
                name="mae",
                role=MetricRole.GUARDRAIL,
                direction=MetricDirection.MINIMIZE,
                evidence_basis=MetricEvidenceBasis.REFERENCE_EVIDENCE,
                max_regression=1.0,
                max_relative_regression=0.1,
                unit="K",
            ),
        ),
        primary_order=("max_abs", "rmse"),
        aggregation_policy=AggregationPolicy.LEXICOGRAPHIC,
    )


def _field(
    path: Path,
    artifact_id: str,
    values: np.ndarray,
    *,
    x: np.ndarray | None = None,
    with_roi: bool = False,
) -> FieldArtifactDescriptor:
    x_values = np.array([0.0, 1.0]) if x is None else x
    payload = {
        "values": values,
        "x": x_values,
        "y": np.array([0.0, 1.0]),
    }
    if with_roi:
        payload["focus_roi"] = np.array(
            [[True, False], [False, False]],
            dtype=bool,
        )
    np.savez(path, **payload)
    return FieldArtifactDescriptor(
        artifact_id=artifact_id,
        path=path.resolve(),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        values_key="values",
        axes=("x", "y"),
        coordinate_keys={"x": "x", "y": "y"},
        roi_mask_keys={"focus": "focus_roi"} if with_roi else {},
        reference_identity="declared-reference-v1",
        unit="K",
        coordinate_system="cartesian-xy",
        normalization="physical-values",
    )


def _invoke(root: Path, contract: PostRunEvaluationContract) -> tuple[int, dict]:
    contract_path = root / f"{contract.evaluation_id}.json"
    contract_path.write_text(contract.model_dump_json(indent=2), encoding="utf-8")
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = main(
            [
                "evaluate",
                "--runtime-root",
                str(root / "runtime"),
                "--contract",
                str(contract_path),
                "--json",
            ]
        )
    return code, json.loads(stream.getvalue())


class PostRunEvaluationTests(unittest.TestCase):
    def test_cli_localizes_max_error_before_lexicographic_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference = _field(
                root / "reference.npz",
                "reference-field",
                np.full((2, 2), 10.0),
                with_roi=True,
            )
            baseline = _field(
                root / "baseline.npz",
                "baseline-field",
                np.array([[14.0, 12.0], [11.0, 11.0]]),
            )
            candidate = _field(
                root / "candidate.npz",
                "candidate-field",
                np.array([[13.0, 12.0], [11.0, 11.0]]),
            )
            contract = PostRunEvaluationContract(
                evaluation_id="evaluation-accepted",
                workflow_id="workflow-post-run",
                run_id="run-candidate",
                observed_failure_mechanism="localized maximum near x=0,y=0",
                baseline=baseline,
                candidate=candidate,
                reference=reference,
                metric_contract=_metric_contract(),
            )

            code, payload = _invoke(root, contract)

            self.assertEqual(code, 0)
            self.assertEqual(payload["code"], "DECISION_ACCEPTED")
            locations = payload["data"]["max_abs_before_decision"]
            self.assertEqual(
                locations["baseline"]["coordinates"],
                {"x": 0.0, "y": 0.0},
            )
            self.assertEqual(locations["baseline"]["absolute_error"], 4.0)
            self.assertEqual(locations["candidate"]["absolute_error"], 3.0)
            self.assertEqual(
                payload["data"]["decision"]["reasons"][0],
                "primary max_abs improved under lexicographic order",
            )
            evidence = payload["data"]["evidence_candidate"]
            self.assertTrue(evidence["ready_for_run_validation"])
            self.assertFalse(evidence["knowledge_promotion_allowed"])
            artifact_root = root / "runtime" / "artifacts" / "evaluations"
            self.assertEqual(len(tuple(artifact_root.glob("*.json"))), 3)
            replay_code, replay_payload = _invoke(root, contract)
            self.assertEqual(replay_code, 0)
            self.assertEqual(replay_payload["code"], "DECISION_ACCEPTED")
            self.assertEqual(len(tuple(artifact_root.glob("*.json"))), 3)

    def test_coordinate_mismatch_is_persisted_as_invalid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference = _field(
                root / "reference.npz",
                "reference-field-invalid",
                np.full((2, 2), 10.0),
            )
            baseline = _field(
                root / "baseline.npz",
                "baseline-field-invalid",
                np.array([[14.0, 12.0], [11.0, 11.0]]),
            )
            candidate = _field(
                root / "candidate.npz",
                "candidate-field-invalid",
                np.array([[13.0, 12.0], [11.0, 11.0]]),
                x=np.array([0.0, 2.0]),
            )
            contract = PostRunEvaluationContract(
                evaluation_id="evaluation-invalid",
                workflow_id="workflow-post-run-invalid",
                run_id="run-candidate-invalid",
                observed_failure_mechanism="candidate grid changed unexpectedly",
                baseline=baseline,
                candidate=candidate,
                reference=reference,
                metric_contract=_metric_contract(),
            )

            code, payload = _invoke(root, contract)

            self.assertEqual(code, 3)
            self.assertEqual(payload["code"], "RESULT_INVALID")
            self.assertEqual(
                payload["data"]["comparison"]["candidate_report"]["status"],
                "RESULT_INVALID",
            )
            self.assertIsNone(
                payload["data"]["max_abs_before_decision"]["candidate"]
            )
            self.assertFalse(
                payload["data"]["evidence_candidate"]["ready_for_run_validation"]
            )
            self.assertFalse(
                payload["data"]["evidence_candidate"]["knowledge_promotion_allowed"]
            )


if __name__ == "__main__":
    unittest.main()

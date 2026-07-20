from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
CASE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ORCHESTRATOR_SRC))
sys.path.insert(0, str(CASE_ROOT))

from pinn_strategy_system.assurance import EvaluationBasisService  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
)

from run_poisson_qualification import (  # noqa: E402
    APPROVAL_SCOPE,
    WORKFLOW_ID,
    _approved_metric_record,
    _case_contracts,
    _collection_directory,
    _execution_approval,
)


class PoissonQualificationContractTests(unittest.TestCase):
    def test_output_channel_unit_is_explicitly_compatible_with_reference(self) -> None:
        worker = (Path(__file__).resolve().parent / "poisson_pinn_worker.py").resolve()
        unit_system, authority, reference, _ = _case_contracts(worker)

        basis = EvaluationBasisService().validate(
            authority=authority,
            references=(reference,),
        )

        self.assertEqual(unit_system.quantity_units["u"], "dimensionless")
        self.assertTrue(basis.ready, basis.reasons)

    def test_collection_destination_has_existing_parent_but_is_new(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = _collection_directory(
                Path(temporary),
                "uniform-smoke",
            )

            self.assertTrue(destination.parent.is_dir())
            self.assertFalse(destination.exists())

    def test_runner_requires_separate_scoped_approvals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = {
                ApprovalKind.METRIC_PRIORITY: root / "metric.json",
                ApprovalKind.EXPERIMENT: root / "execution.json",
            }
            for kind, path in records.items():
                path.write_text(
                    ApprovalRecord(
                        approval_id=f"test-{kind.value.lower()}",
                        workflow_id=WORKFLOW_ID,
                        kind=kind,
                        decision=ApprovalDecision.APPROVED,
                        approved_by="test-user",
                        approved_at=datetime.now(UTC),
                        scope=APPROVAL_SCOPE,
                    ).model_dump_json(indent=2),
                    encoding="utf-8",
                )

            self.assertEqual(
                _approved_metric_record(records[ApprovalKind.METRIC_PRIORITY]).kind,
                ApprovalKind.METRIC_PRIORITY,
            )
            self.assertEqual(
                _execution_approval(records[ApprovalKind.EXPERIMENT]).kind,
                ApprovalKind.EXPERIMENT,
            )
            with self.assertRaises(ValueError):
                _execution_approval(records[ApprovalKind.METRIC_PRIORITY])


if __name__ == "__main__":
    unittest.main()

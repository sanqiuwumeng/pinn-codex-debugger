from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
CASE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ORCHESTRATOR_SRC))
sys.path.insert(0, str(CASE_ROOT))

from pinn_strategy_system.assurance import EvaluationBasisService  # noqa: E402

from run_poisson_qualification import (  # noqa: E402
    _case_contracts,
    _collection_directory,
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


if __name__ == "__main__":
    unittest.main()

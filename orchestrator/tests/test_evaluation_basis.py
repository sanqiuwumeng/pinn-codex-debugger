from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinn_strategy_system.assurance import EvaluationBasisService  # noqa: E402
from pinn_strategy_system.contracts import (  # noqa: E402
    ArtifactRef,
    PhysicalModelAuthority,
    ReferenceEvidence,
    ReferenceKind,
    SourceRef,
    UnitSystemContract,
)

SHA = "9" * 64


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        uri=f"artifact://evaluation-basis/{name}",
        sha256=SHA,
    )


def source() -> SourceRef:
    return SourceRef(
        uri="file:///project/model.py",
        sha256=SHA,
        line_start=1,
        line_end=10,
    )


def authority() -> PhysicalModelAuthority:
    return PhysicalModelAuthority(
        authority_id="authority-1",
        project_id="project-1",
        model_family="pinn",
        pde_family="heat-equation",
        task_type="forward",
        governing_equation_refs=(source(),),
        output_channels=("temperature",),
        unit_system=UnitSystemContract(
            unit_system_id="case-units",
            name="case units",
            quantity_units={"temperature": "K", "length": "mm"},
            source_refs=(source(),),
            confirmed_by_user=True,
        ),
        confirmed_by_user=True,
    )


def reference(*, authority_id: str = "authority-1", unit: str = "K"):
    return ReferenceEvidence(
        reference_id="fem-case-reference",
        authority_id=authority_id,
        kind=ReferenceKind.NUMERICAL,
        artifact_ref=artifact("fem-field"),
        output_channels=("temperature",),
        coordinate_system="cartesian-mm",
        channel_units={"temperature": unit},
        test_case_only=True,
    )


class EvaluationBasisTests(unittest.TestCase):
    def test_compatible_case_reference_is_not_a_universal_truth(self) -> None:
        result = EvaluationBasisService().validate(
            authority=authority(),
            references=(reference(),),
        )

        self.assertTrue(result.ready)
        self.assertTrue(result.checks["reference:fem-case-reference:authority"])

    def test_reference_from_another_model_is_rejected(self) -> None:
        result = EvaluationBasisService().validate(
            authority=authority(),
            references=(reference(authority_id="authority-2"),),
        )

        self.assertFalse(result.ready)
        self.assertTrue(any("another physical authority" in item for item in result.reasons))

    def test_reference_free_physical_model_is_a_valid_basis(self) -> None:
        result = EvaluationBasisService().validate(authority=authority())

        self.assertTrue(result.ready)

    def test_reference_channel_unit_must_match_the_model(self) -> None:
        result = EvaluationBasisService().validate(
            authority=authority(),
            references=(reference(unit="m/s"),),
        )

        self.assertFalse(result.ready)
        self.assertFalse(result.checks["reference:fem-case-reference:unit:temperature"])


if __name__ == "__main__":
    unittest.main()

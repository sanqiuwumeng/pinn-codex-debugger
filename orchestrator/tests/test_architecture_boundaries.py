from __future__ import annotations

import ast
import unittest
from pathlib import Path

PACKAGE_ROOT = (
    Path(__file__).resolve().parents[1] / "src" / "pinn_strategy_system"
)
BANNED_IMPORT_ROOTS = {
    "torch",
    "tensorflow",
    "deepxde",
    "rules_mcp",
    "hybrid_rag",
    "pinn_hybrid_rag",
}


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_runtime_has_no_training_or_mcp_implementation_imports(self) -> None:
        violations: list[str] = []
        for path, tree in _production_trees():
            for node in ast.walk(tree):
                imported: tuple[str, ...] = ()
                if isinstance(node, ast.Import):
                    imported = tuple(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported = (node.module,)
                for module in imported:
                    if module.split(".", 1)[0] in BANNED_IMPORT_ROOTS:
                        violations.append(f"{path.name}:{node.lineno}:{module}")
        self.assertEqual(violations, [])

    def test_runtime_declares_no_global_or_nonlocal_business_transport(self) -> None:
        violations: list[str] = []
        for path, tree in _production_trees():
            for node in ast.walk(tree):
                if isinstance(node, (ast.Global, ast.Nonlocal)):
                    violations.append(
                        f"{path.name}:{node.lineno}:{type(node).__name__}"
                    )
        self.assertEqual(violations, [])

    def test_runtime_has_no_module_level_mutable_literal_state(self) -> None:
        violations: list[str] = []
        for path, tree in _production_trees():
            for node in tree.body:
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = (
                        node.targets
                        if isinstance(node, ast.Assign)
                        else (node.target,)
                    )
                    if all(
                        isinstance(target, ast.Name)
                        and target.id == "__all__"
                        for target in targets
                    ):
                        continue
                    value = node.value
                    if isinstance(value, (ast.List, ast.Dict, ast.Set)):
                        violations.append(
                            f"{path.name}:{node.lineno}:{type(value).__name__}"
                        )
        self.assertEqual(violations, [])

    def test_runtime_does_not_use_implicit_working_directory(self) -> None:
        forbidden = {("os", "getcwd"), ("os", "chdir"), ("Path", "cwd")}
        violations: list[str] = []
        for path, tree in _production_trees():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                if isinstance(function, ast.Attribute) and isinstance(
                    function.value, ast.Name
                ):
                    name = (function.value.id, function.attr)
                    if name in forbidden:
                        violations.append(f"{path.name}:{node.lineno}:{name}")
        self.assertEqual(violations, [])

    def test_generic_prediction_analyzer_has_no_thermal_semantics(self) -> None:
        prediction_module = PACKAGE_ROOT / "execution" / "prediction.py"
        source = prediction_module.read_text(encoding="utf-8").casefold()
        forbidden = (
            "temperature",
            "solidus",
            "liquidus",
            "mushy",
            "phase_metric",
            "liquid_mask",
            "heat_transfer",
        )
        self.assertEqual(
            tuple(term for term in forbidden if term in source),
            (),
        )

    def test_domain_metric_package_entrypoint_loads_interfaces_only(self) -> None:
        entrypoint = PACKAGE_ROOT / "domain_metrics" / "__init__.py"
        source = entrypoint.read_text(encoding="utf-8").casefold()
        self.assertNotIn("heat_transfer", source)
        self.assertNotIn("residual", source)


def _production_trees():
    for path in PACKAGE_ROOT.rglob("*.py"):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


if __name__ == "__main__":
    unittest.main()

"""Product composition-root and handbook-location regression tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pinn_hybrid_rag.__main__ import (
    HANDBOOK_ENV_VAR,
    default_handbook_path,
)

from .support import repo_root


class ProductEntrypointTests(unittest.TestCase):
    def test_source_tree_prefers_repository_handbook(self) -> None:
        self.assertEqual(
            default_handbook_path(repo_root()),
            (repo_root() / "PINN报错诊断与模块选择手册.md").resolve(),
        )

    def test_non_source_root_uses_packaged_handbook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            selected = default_handbook_path(Path(temp_dir))

        self.assertEqual(selected.parent.name, "resources")
        self.assertEqual(selected.name, "PINN报错诊断与模块选择手册.md")
        self.assertTrue(selected.exists())

    def test_environment_override_has_highest_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            override = Path(temp_dir) / "custom-handbook.md"
            with patch.dict(os.environ, {HANDBOOK_ENV_VAR: str(override)}):
                selected = default_handbook_path(repo_root())

        self.assertEqual(selected, override.resolve())


if __name__ == "__main__":
    unittest.main()

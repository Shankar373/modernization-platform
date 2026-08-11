"""Dynamic pyproject.toml generator for Python migrations."""
from pathlib import Path
from typing import Optional

import toml

from app.core.domain.models import MigrationPlan, MigrationProfile


_VERSION_MAP = {
    "3.6": "py36", "3.7": "py37", "3.8": "py38",
    "3.9": "py39", "3.10": "py310", "3.11": "py311", "3.12": "py312",
}


class PyprojectGenerator:
    """
    Generates or updates pyproject.toml with Ruff configuration
    appropriate for the target Python version and migration profile.
    """

    def generate(
        self,
        workspace_path: str,
        target_version: str,
        plan: MigrationPlan,
        output_path: Optional[str] = None,
    ) -> str:
        ws = Path(workspace_path)
        existing_path = ws / "pyproject.toml"

        if existing_path.exists():
            try:
                config = toml.load(str(existing_path))
            except Exception:
                config = {}
        else:
            config = {}

        ruff_target = _VERSION_MAP.get(target_version, "py311")
        is_aggressive = plan.profile == MigrationProfile.AGGRESSIVE
        is_standard = plan.profile in (MigrationProfile.STANDARD, MigrationProfile.AGGRESSIVE)

        # Build Ruff config
        ruff_config = {
            "target-version": ruff_target,
            "line-length": 88,
            "indent-width": 4,
        }

        # Lint rules — expand based on profile
        select_rules = ["E", "F"]  # Always: pycodestyle errors + pyflakes
        if is_standard:
            select_rules += ["I", "UP"]  # isort + pyupgrade
        if is_aggressive:
            select_rules += ["B", "C4", "SIM"]  # flake8-bugbear, comprehensions, simplify

        ruff_config["lint"] = {
            "select": select_rules,
            "ignore": ["E501"],  # Don't enforce line length via lint (formatter handles it)
            "fixable": ["ALL"],
            "unfixable": [],
        }

        ruff_config["format"] = {
            "quote-style": "double",
            "indent-style": "space",
            "skip-magic-trailing-comma": False,
            "line-ending": "auto",
        }

        # Preserve existing config, overlay Ruff section
        if "tool" not in config:
            config["tool"] = {}
        config["tool"]["ruff"] = ruff_config

        out = output_path or str(ws / "pyproject.toml")
        with open(out, "w", encoding="utf-8") as f:
            toml.dump(config, f)

        return out

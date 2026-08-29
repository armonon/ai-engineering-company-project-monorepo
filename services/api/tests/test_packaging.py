"""Packaging checks for executable API entry points.

Tests usually import from the source checkout, which can hide a missing
``py-modules`` declaration. Console scripts execute from the installer's bin
directory instead, so every top-level module referenced by ``project.scripts``
must be part of the installed distribution.
"""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_every_console_script_module_is_packaged() -> None:
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    scripts = config["project"]["scripts"]
    packaged_modules = set(config["tool"]["setuptools"]["py-modules"])
    script_modules = {target.partition(":")[0] for target in scripts.values()}

    assert script_modules <= packaged_modules, (
        "console-script modules missing from tool.setuptools.py-modules: "
        f"{sorted(script_modules - packaged_modules)}"
    )


def test_inventory_router_package_is_included_in_distribution() -> None:
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    package_patterns = config["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "routers*" in package_patterns


def test_inventory_schema_module_is_included_in_distribution() -> None:
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert "schemas" in config["tool"]["setuptools"]["py-modules"]

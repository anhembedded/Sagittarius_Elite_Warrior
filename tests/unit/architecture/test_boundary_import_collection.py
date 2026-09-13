"""The import reader sees what it must and ignores what it must
(`boundaries/imports.py`). A guard that cannot see a violation is a fake gate."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.imports import (
    imported_modules,
)

_HANDLER = "application.use_cases.x.handler"


def test_absolute_imports_lose_the_repository_prefix() -> None:
    source = (
        "from Sagittarius_Elite_Warrior.src.infrastructure.binance.client import Client\n"
        "import Sagittarius_Elite_Warrior.src.infrastructure.persistence.repo\n"
    )
    assert imported_modules(_HANDLER, source) == {
        "infrastructure.binance.client",
        "infrastructure.persistence.repo",
    }


def test_relative_imports_resolve_against_the_importing_module() -> None:
    source = "from ...ports.i_cqrs import ICommandHandler\nfrom .command import C\n"
    assert imported_modules(_HANDLER, source) == {
        "application.ports.i_cqrs",
        "application.use_cases.x.command",
    }


def test_relative_import_from_a_package_init_resolves_against_the_package() -> None:
    found = imported_modules(
        "application.use_cases.x", "from .handler import H\n", is_package=True
    )
    assert found == {"application.use_cases.x.handler"}


def test_type_checking_imports_are_ignored_but_the_else_branch_is_not() -> None:
    source = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from Sagittarius_Elite_Warrior.src.infrastructure.binance.client import Client\n"
        "else:\n"
        "    from Sagittarius_Elite_Warrior.src.domain.trading.order import Order\n"
    )
    assert imported_modules(_HANDLER, source) == {"typing", "domain.trading.order"}


def test_outside_imports_come_back_unchanged() -> None:
    source = "import logging\nfrom PySide6.QtCore import QObject\n"
    assert imported_modules(_HANDLER, source) == {"logging", "PySide6.QtCore"}

"""`BOT-200` — `key check` is declared once, in the places that decide how it runs."""

from __future__ import annotations

import argparse
import json

from Sagittarius_Elite_Warrior.src.modules.trading.cli.key_cli_handler import (
    KeyCliHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.module import TradingModule
from Sagittarius_Elite_Warrior.src.shell.app_config import CLI_COMMANDS_FILE
from Sagittarius_Elite_Warrior.src.shell.cli_registry import CliRegistry
from Sagittarius_Elite_Warrior.src.support.cli_host.command_access import (
    command_is_read_only,
    command_needed_modules,
    command_requires_writable_instance,
)

_ARGS = argparse.Namespace(command="key", action="check")


def _shipped() -> dict[str, object]:
    return json.loads(CLI_COMMANDS_FILE.read_text(encoding="utf-8"))["CLI_COMMANDS"]


def test_the_trading_module_declares_key_with_its_handler() -> None:
    registry = CliRegistry()

    TradingModule().declare_cli(registry)

    assert registry.handlers()["key"] is KeyCliHandler


def test_key_check_needs_no_writable_data_root_and_builds_only_trading() -> None:
    shipped = _shipped()

    assert command_is_read_only(shipped, _ARGS) is True
    assert command_requires_writable_instance(shipped, _ARGS) is False
    assert command_needed_modules(shipped, _ARGS) == frozenset({"trading"})


def test_no_argument_can_carry_a_key_or_a_secret() -> None:
    """A value in an argument is in the process list and the shell history; the
    declaration offers the output format and nothing else."""
    entry = _shipped()["key"]["subparsers"]["commands"]["check"]  # type: ignore[index]

    assert {arg["name"] for arg in entry["args"]} == {"--json", "--format"}

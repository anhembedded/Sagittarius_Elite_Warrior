"""A backtest's sandbox plan writes no bot, sends no order and reads no account (`EPIC-040C`).

The sandbox is a simulation: a copy of a bot's saved plan, judged by the symbol's rules and replayed
over stored candles. If its code could reach a command, the bot store or runner, the venue's order
ports or the account's reads, a "what if" could become a real action. So the files of the sandbox
(the plan value and the `ui/backtest/` package) import none of them: not a command or its handler
(`bots.application.use_cases`), not the command dispatcher, not the bot store or runner, not the
venue's trading ports, accounts or facts, not the exposure book. The sandbox's only collaborators are
the kind's `validate` and `IKindBacktester`, and the planner's read-only terms.

There is no baseline: the sandbox imports none today, and a new import is a failure.

Retire when: never; the ban stays as long as the sandbox is a simulation.
"""

from __future__ import annotations

import ast
from pathlib import Path

from .test_bots_services_stay_grouped import _REPO_ROOT

_BOTS = _REPO_ROOT / "src" / "modules" / "bots"
_SANDBOX_FILES = (_BOTS / "domain" / "backtest" / "sandbox_plan.py",)
_SANDBOX_PACKAGES = (_BOTS / "ui" / "backtest",)
_PREFIX = "Sagittarius_Elite_Warrior.src."

#: What the sandbox may never import: a module (by prefix) that holds a command or a real-money port.
FORBIDDEN_MODULES = (
    "modules.bots.application.use_cases",
    "modules.bots.contracts.host_bot_requests",
    "modules.bots.contracts.i_bot_store",
    "modules.bots.contracts.i_bot_runner",
    "modules.bots.contracts.i_venue_facts",
    "modules.bots.contracts.i_exposure_book",
    "modules.bots.contracts.i_exposure_closer",
    "modules.bots.contracts.i_risk_guard",
    "modules.bots.contracts.i_order_pacer",
    "core.contracts.i_command_dispatcher",
    "modules.trading.contracts.i_venue_trading_ports",
    "modules.trading.contracts.i_venue_accounts",
    "modules.trading.contracts.i_order_entry_terms",
)


def _sandbox_files() -> list[Path]:
    files = [path for package in _SANDBOX_PACKAGES for path in package.rglob("*.py")]
    return sorted([*_SANDBOX_FILES, *files])


def forbidden_imports(path: Path) -> list[str]:
    """The forbidden modules `path` imports, from its syntax tree."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.removeprefix(_PREFIX)
        elif isinstance(node, ast.Import):
            module = " ".join(alias.name.removeprefix(_PREFIX) for alias in node.names)
        else:
            continue
        found += [m for m in FORBIDDEN_MODULES if module.startswith(m)]
    return found


def test_the_sandbox_imports_no_command_and_no_real_money_port() -> None:
    found = {
        path.relative_to(_REPO_ROOT).as_posix(): hits
        for path in _sandbox_files()
        if (hits := forbidden_imports(path))
    }

    assert found == {}, (
        f"the sandbox reaches a command or a real-money port: {found}. A simulation sends "
        "no command, opens no order session and reads no account (`EPIC-040C`)."
    )


def test_the_guard_has_a_subject() -> None:
    files = _sandbox_files()

    assert len(files) >= 3, files
    assert all(path.is_file() for path in files), [p for p in files if not p.is_file()]


def test_a_probe_importing_a_command_or_a_port_turns_the_scan_red(
    tmp_path: Path,
) -> None:
    clean = tmp_path / "clean.py"
    clean.write_text("from decimal import Decimal\n", encoding="utf-8")
    for name, source in {
        "command.py": f"from {_PREFIX}modules.bots.application.use_cases.start_bot.command import StartBotCommand\n",
        "dispatcher.py": f"from {_PREFIX}core.contracts.i_command_dispatcher import ICommandDispatcher\n",
        "store.py": f"from {_PREFIX}modules.bots.contracts.i_bot_store import IBotStore\n",
        "accounts.py": f"from {_PREFIX}modules.trading.contracts.i_venue_accounts import IVenueAccounts\n",
        "plain.py": f"import {_PREFIX}modules.trading.contracts.i_venue_trading_ports\n",
    }.items():
        probe = tmp_path / name
        probe.write_text(source, encoding="utf-8")

        assert forbidden_imports(clean) == []
        assert forbidden_imports(probe), name

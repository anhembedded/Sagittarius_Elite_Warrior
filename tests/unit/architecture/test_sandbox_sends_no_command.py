"""A backtest's sandbox plan writes no bot, sends no order and reads no account (`EPIC-040C`).

The sandbox is a simulation: a copy of a bot's saved plan, judged by the symbol's rules and replayed
over stored candles. If its code could reach a command, the bot store or runner, the venue's order
ports or the account's reads, a "what if" could become a real action. So this is an **allow-list**:
the files of the sandbox (the plan value and the `ui/backtest/` package) may import only the modules
named in `ALLOWED_PROJECT_MODULES`, which are values, the kind's `validate` and the planner's
read-only terms. A new import of a project module fails the scan until someone names it here, which
is how a boundary on real money should fail: a deny-list passes every port nobody thought of
(`i_order_submission`, `i_account_activity`, a new reader). Imports are read from the syntax tree,
each alias and each `from package import module` form included. A relative import fails (the
project writes absolute ones). A dynamic `importlib.import_module(...)` is outside this scan: the
guard stops a careless import, not a deliberate evasion, which a review reads.

There is no baseline: the sandbox imports nothing else today.

Retire when: never; the ban stays as long as the sandbox is a simulation.
"""

from __future__ import annotations

import ast
from pathlib import Path

from .test_bots_services_stay_grouped import _REPO_ROOT

_BOTS = _REPO_ROOT / "src" / "modules" / "bots"
_SANDBOX_FILES = (_BOTS / "domain" / "backtest" / "sandbox_plan.py",)
_SANDBOX_PACKAGES = (_BOTS / "ui" / "backtest",)
_ROOT = "Sagittarius_Elite_Warrior."
_PREFIX = _ROOT + "src."

#: The only project modules the sandbox may import (paths below `src.`).
ALLOWED_PROJECT_MODULES = frozenset(
    {
        "modules.bots.application.queries.get_planner_market.result",
        "modules.bots.contracts.bot_snapshot",
        "modules.bots.contracts.i_bot_kind",
        "modules.bots.contracts.venue_profile",
        "modules.bots.domain.backtest.sandbox_plan",
        "modules.bots.domain.bot_kind_inputs",
        "modules.bots.domain.verdict",
        "modules.bots.ui.bots_screen.bot_plan_judge",
        "support.binance_gateway.contracts.trading_venue",
    }
)


def _sandbox_files() -> list[Path]:
    files = [path for package in _SANDBOX_PACKAGES for path in package.rglob("*.py")]
    return sorted([*_SANDBOX_FILES, *files])


def _imports(tree: ast.AST) -> list[tuple[str, bool]]:
    """Every module a file imports, as written, and whether the name could be a symbol: for
    `from m import n` the module `m` (written in the source, so it must match exactly) and `m.n`
    (which may be a symbol of `m`, or a module of its own); `.` marks a relative import."""
    found: list[tuple[str, bool]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                found.append((".", False))
            elif node.module:
                found.append((node.module, False))
                found += [(f"{node.module}.{alias.name}", True) for alias in node.names]
        elif isinstance(node, ast.Import):
            found += [(alias.name, False) for alias in node.names]
    return found


def unlisted_imports(path: Path) -> list[str]:
    """The project modules `path` imports that the allow-list does not name. A module path written
    in the source must be named exactly: a submodule of an allowed module is another module (the
    allowed package `get_planner_market` re-exports a handler that reads the account)."""
    unlisted = []
    for module, may_be_symbol in _imports(ast.parse(path.read_text(encoding="utf-8"))):
        if module == ".":
            unlisted.append(module)
            continue
        if not module.startswith(_ROOT):
            continue
        name = module.removeprefix(_PREFIX)
        if name in ALLOWED_PROJECT_MODULES:
            continue
        if may_be_symbol and name.rpartition(".")[0] in ALLOWED_PROJECT_MODULES:
            continue  # `from allowed import Symbol`
        unlisted.append(name)
    return unlisted


def test_the_sandbox_imports_only_what_the_allow_list_names() -> None:
    found = {
        path.relative_to(_REPO_ROOT).as_posix(): hits
        for path in _sandbox_files()
        if (hits := unlisted_imports(path))
    }

    assert found == {}, (
        f"the sandbox imports a project module the allow-list does not name: {found}. A "
        "simulation sends no command, opens no order session and reads no account "
        "(`EPIC-040C`); if the new import is a value or a read-only term, name it in "
        "ALLOWED_PROJECT_MODULES with the reason."
    )


def test_every_allowed_module_exists() -> None:
    missing = [
        name
        for name in sorted(ALLOWED_PROJECT_MODULES)
        if not (_REPO_ROOT / "src" / Path(*name.split(".")))
        .with_suffix(".py")
        .is_file()
        and not (_REPO_ROOT / "src" / Path(*name.split(".")) / "__init__.py").is_file()
    ]

    assert missing == [], f"the allow-list names a module that is gone: {missing}"


def test_the_guard_has_a_subject() -> None:
    files = _sandbox_files()

    assert len(files) >= 3, files
    assert all(path.is_file() for path in files), [p for p in files if not p.is_file()]


def test_a_probe_turns_the_scan_red_for_every_form_of_import(tmp_path: Path) -> None:
    allowed = (
        f"from {_PREFIX}modules.bots.domain.verdict import Verdict\n"
        f"from {_PREFIX}modules.bots.application.queries.get_planner_market.result import PlannerMarket\n"
    )
    clean = tmp_path / "clean.py"
    clean.write_text(
        "from decimal import Decimal\nimport dataclasses\n" + allowed, encoding="utf-8"
    )
    assert unlisted_imports(clean) == []
    probes = {
        "command.py": f"from {_PREFIX}modules.bots.application.use_cases.start_bot.command import StartBotCommand\n",
        "dispatcher.py": f"from {_PREFIX}core.contracts.i_command_dispatcher import ICommandDispatcher\n",
        "package_then_name.py": f"from {_PREFIX}modules.trading.contracts import i_venue_accounts\n",
        "second_alias.py": f"import decimal, {_PREFIX}modules.trading.contracts.i_venue_trading_ports\n",
        "a_port_nobody_listed.py": f"from {_PREFIX}modules.trading.contracts.i_order_submission import IOrderSubmission\n",
        "account_activity.py": f"from {_PREFIX}modules.trading.contracts.i_account_activity import IAccountActivity\n",
        "relative.py": "from . import sandbox_plan\n",
        "package_reexport.py": f"from {_PREFIX}modules.bots.application.queries.get_planner_market import GetPlannerMarketQueryHandler\n",
        "submodule_of_allowed.py": f"from {_PREFIX}modules.bots.application.queries.get_planner_market.handler import GetPlannerMarketQueryHandler\n",
        "submodule_import.py": f"import {_PREFIX}modules.bots.contracts.venue_profile.anything\n",
    }
    for name, source in probes.items():
        probe = tmp_path / name
        probe.write_text(source, encoding="utf-8")

        assert unlisted_imports(probe), name

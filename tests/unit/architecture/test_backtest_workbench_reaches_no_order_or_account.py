"""The Backtest workbench starts a replay and nothing that touches money (`EPIC-040D`).

The workbench holds the dispatcher (to run `RunBacktestQuery`) and an editor, so it sits one import
from a command. Its sandbox core is guarded exactly (`test_sandbox_sends_no_command.py`); this guard
covers the rest of the package and is an **allow-list over the sensitive families**: a project import
under `modules/trading`, `modules/bots/application`, `modules/bots/adapters`, `modules/bots/composition`,
`support/binance_gateway`, the bot runner and executor ports, or the command dispatcher must be named in
`ALLOWED_SENSITIVE_MODULES`. The authority the package holds is narrowed by type: it is handed a
`Callable[[RunBacktestQuery], BacktestAnswer]`, never a dispatcher, so no command is in reach; and a
syntax check bans the two things an `IBotKind` offers that start a bot (`executor_factory`,
`recovery_layer`). The runtime half is the integration test (`EPIC-040C`): a sandbox run over watched ports.

Retire when: never; the ban stays as long as the workbench is a simulation.
"""

from __future__ import annotations

import ast
from pathlib import Path

from .test_bots_services_stay_grouped import _REPO_ROOT
from .test_sandbox_sends_no_command import _imports

_PACKAGE = _REPO_ROOT / "src" / "modules" / "bots" / "ui" / "backtest_workbench"
_ROOT = "Sagittarius_Elite_Warrior."
_PREFIX = _ROOT + "src."
_SENSITIVE = (
    "modules.trading.",
    "modules.bots.application.",
    "modules.bots.adapters.",
    "modules.bots.composition.",
    "infrastructure.",
    "support.binance_gateway.",
    "modules.bots.contracts.i_bot_executor",
    "modules.bots.contracts.i_bot_runner",
    "modules.bots.contracts.i_bot_store",
    "core.contracts.i_command_dispatcher",
)
#: What a kind offers that starts or recovers a bot: never read by the workbench.
BANNED_ATTRIBUTES = frozenset({"executor_factory", "recovery_layer"})

#: The sensitive modules the workbench may import, and why each is safe.
ALLOWED_SENSITIVE_MODULES = frozenset(
    {
        # a read-only value the planner reads
        "modules.bots.application.queries.get_planner_market.result",
        # the one query the workbench runs: it replays stored candles
        "modules.bots.application.queries.run_backtest",
        # a value: which venue a bot trades on
        "support.binance_gateway.contracts.trading_venue",
        # a value: the side of a replayed fill
        "modules.trading.contracts.order_side",
    }
)


def _files() -> list[Path]:
    return sorted(_PACKAGE.rglob("*.py"))


def unlisted_sensitive_imports(path: Path) -> list[str]:
    found = []
    for module, may_be_symbol in _imports(ast.parse(path.read_text(encoding="utf-8"))):
        if not module.startswith(_PREFIX):
            continue
        name = module.removeprefix(_PREFIX)
        if not name.startswith(_SENSITIVE) and name + "." not in _SENSITIVE:
            continue
        if name in ALLOWED_SENSITIVE_MODULES:
            continue
        if may_be_symbol and name.rpartition(".")[0] in ALLOWED_SENSITIVE_MODULES:
            continue
        found.append(name)
    return found


def test_the_workbench_imports_no_order_account_or_command_code() -> None:
    found = {
        path.relative_to(_REPO_ROOT).as_posix(): hits
        for path in _files()
        if (hits := unlisted_sensitive_imports(path))
    }

    assert found == {}, (
        f"the workbench imports money-adjacent code the allow-list does not name: {found}. "
        "A simulation starts no bot, sends no order and reads no account (`EPIC-040D`); if the "
        "import is a value or a read-only query, name it in ALLOWED_SENSITIVE_MODULES."
    )


def _banned_uses(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and (node.attr in BANNED_ATTRIBUTES or node.attr == "dispatch")
    ]


def test_the_workbench_dispatches_nothing_and_never_starts_a_kinds_executor() -> None:
    found = {
        path.relative_to(_REPO_ROOT).as_posix(): uses
        for path in _files()
        if (uses := _banned_uses(path))
    }

    assert found == {}, (
        f"the workbench calls {found}: it is handed the one query it runs, not a dispatcher, "
        "and it never asks a kind for an executor (`EPIC-040D`)."
    )


def test_every_allowed_module_exists() -> None:
    missing = [
        name
        for name in sorted(ALLOWED_SENSITIVE_MODULES)
        if not (_REPO_ROOT / "src" / Path(*name.split(".")))
        .with_suffix(".py")
        .is_file()
        and not (_REPO_ROOT / "src" / Path(*name.split(".")) / "__init__.py").is_file()
    ]

    assert missing == [], f"the allow-list names a module that is gone: {missing}"


def test_the_guard_has_a_subject() -> None:
    assert len(_files()) >= 10, _files()


def test_a_probe_turns_the_scan_red(tmp_path: Path) -> None:
    clean = tmp_path / "clean.py"
    clean.write_text(
        f"from {_PREFIX}modules.trading.contracts.order_side import OrderSide\n"
        f"from {_PREFIX}modules.bots.application.queries.run_backtest import RunBacktestQuery\n",
        encoding="utf-8",
    )
    assert unlisted_sensitive_imports(clean) == []
    probes = {
        "command.py": f"from {_PREFIX}modules.bots.application.use_cases.start_bot.command import StartBotCommand\n",
        "port.py": f"from {_PREFIX}modules.trading.contracts.i_order_submission import IOrderSubmission\n",
        "package_then_name.py": f"from {_PREFIX}modules.trading.contracts import i_venue_accounts\n",
        "adapter.py": f"from {_PREFIX}modules.bots.adapters.venue_fresh_price_reader import VenueFreshPriceReader\n",
        "composition.py": f"import {_PREFIX}modules.bots.composition.executor_bindings\n",
        "handler.py": f"from {_PREFIX}modules.bots.application.queries.get_planner_market.handler import GetPlannerMarketQueryHandler\n",
        "gateway.py": f"from {_PREFIX}support.binance_gateway.adapters.binance_client import BinanceClient\n",
        "executor.py": f"from {_PREFIX}modules.bots.contracts.i_bot_executor import IBotExecutor\n",
        "dispatcher.py": f"from {_PREFIX}core.contracts.i_command_dispatcher import ICommandDispatcher\n",
    }
    for name, source in probes.items():
        probe = tmp_path / name
        probe.write_text(source, encoding="utf-8")

        assert unlisted_sensitive_imports(probe) != [], name


def test_a_probe_turns_the_attribute_scan_red(tmp_path: Path) -> None:
    clean = tmp_path / "clean.py"
    clean.write_text("kind.validate(inputs)\nkind.backtester()\n", encoding="utf-8")
    assert _banned_uses(clean) == []
    for name, source in {
        "executor.py": "kind.executor_factory()\n",
        "recovery.py": "kind.recovery_layer\n",
        "dispatch.py": "dispatcher.dispatch(StartBotCommand, command)\n",
    }.items():
        probe = tmp_path / name
        probe.write_text(source, encoding="utf-8")

        assert _banned_uses(probe) != [], name

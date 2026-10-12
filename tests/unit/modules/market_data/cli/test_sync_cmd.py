"""`EPIC-018F` — `execute_sync()`'s headless (non-interactive) CLI path.

Only covers the fix this task made: a real `dispatch()` failure must be
reported and exit non-zero instead of propagating as an uncaught
traceback — same class of bug `sync_cli_handler.py` (interactive path)
already had fixed, that this headless sibling still had.

`EPIC-038B` — the failure is a returned `CliOutcome`, not a `sys.exit(1)` inside
the command: the same path, now one a test reads without catching `SystemExit`,
and `run_command` turns it into the documented status. The assertion that the
process would exit 1 is kept, one layer out.
"""

from argparse import Namespace

from binance.exceptions import BinanceRequestException
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.sync_cmd import execute_sync
from Sagittarius_Elite_Warrior.src.support.cli_host.exit_status import run_command
from Sagittarius_Elite_Warrior.tests.unit.modules.market_data.cli.dispatching_app import (
    dispatching_app,
)


def _args(**overrides) -> Namespace:
    base = {"symbols": "BTCUSDT", "interval": "1m", "days": 30}
    base.update(overrides)
    return Namespace(**base)


def test_execute_sync_dispatches_command(capsys):
    app, dispatcher = dispatching_app()

    execute_sync(app, _args())

    args, _ = dispatcher.dispatch.call_args
    assert args[0] == SyncMarketDataCommand


def test_a_successful_sync_exits_zero():
    app, _dispatcher = dispatching_app()

    assert run_command(lambda: execute_sync(app, _args())) == 0


def test_execute_sync_dispatch_raises_reports_and_exits(capsys):
    app, _dispatcher = dispatching_app(raises=ConnectionError("Network error"))

    outcome = execute_sync(app, _args())

    assert outcome == CliOutcome(ExitCode.ERROR)
    captured = capsys.readouterr()
    assert "❌ Sync failed: Network error" in captured.out


def test_a_failed_sync_exits_with_the_documented_code():
    app, _dispatcher = dispatching_app(raises=ConnectionError("Network error"))

    assert run_command(lambda: execute_sync(app, _args())) == int(ExitCode.ERROR)


def test_a_sync_the_command_rejects_exits_with_the_usage_code(capsys):
    """An empty symbol list fails the command's own validation: the request is
    unusable, which is exit 2, not the "unexpected" 1 of a network failure."""
    app, _dispatcher = dispatching_app(raises=ValueError("symbols must not be empty"))

    outcome = execute_sync(app, _args())

    assert outcome == CliOutcome(ExitCode.USAGE)
    assert "symbols must not be empty" in capsys.readouterr().out


def test_an_exchange_failure_during_sync_is_the_exchange_code():
    """A rejected request or an unreachable host is not "unexpected": a
    supervisor retries it after a delay, where it would restart an error."""
    app, _dispatcher = dispatching_app(raises=BinanceRequestException("boom"))

    assert run_command(lambda: execute_sync(app, _args())) == int(ExitCode.EXCHANGE)

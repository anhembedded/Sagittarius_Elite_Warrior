"""`sync` at the prompt, from parsed arguments to one dispatched command.

`EPIC-025` PR 0.4a-2 moved parsing out of the handler, so the two cases that
used to live here — a missing required argument, and `-h` — moved with it, to
`tests/unit/presentation/cli/test_interactive_shell.py`. They were never
assertions about syncing; they were assertions about argparse, made through a
handler that happened to own a parser. What is left here is what this handler
actually decides: how a parsed line becomes a `SyncMarketDataCommand`, and what
the user is told when it fails.
"""

from argparse import Namespace

from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.sync_cli_handler import (
    SyncCliHandler,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.market_data.cli.dispatching_app import (
    dispatching_app,
)


def _args(symbols: str, interval: str = "1m", days: int = 30) -> Namespace:
    """What `build_handler_parser(config, "sync")` produces for this command —
    the three arguments `cli_commands.json` declares, defaults applied."""
    return Namespace(symbols=symbols, interval=interval, days=days)


def test_a_parsed_line_becomes_one_command_with_upper_cased_symbols():
    # SyncMarketDataCommandHandler.execute() returns None on success — no
    # response object with a `.success` field (unlike Start/Stop Stream).
    app, dispatcher = dispatching_app()

    SyncCliHandler.handle(_args("ethusdt, btcusdt", interval="1m", days=2), app)

    dispatcher.dispatch.assert_called_once()
    args, _ = dispatcher.dispatch.call_args
    assert args[0] == SyncMarketDataCommand
    cmd = args[1]
    assert cmd.symbols == ["ETHUSDT", "BTCUSDT"]
    assert cmd.days_back_if_empty == 2


def test_success_says_so(capsys):
    app, _dispatcher = dispatching_app()

    SyncCliHandler.handle(_args("BTCUSDT"), app)

    assert "✅ Sync complete." in capsys.readouterr().out


def test_a_failure_is_reported_not_raised(capsys):
    """A real sync failure (network, DB) raises out of dispatch() rather than
    returning a success=False result — see BulkSyncMarketDataCommandHandler's
    own handling of this same command. The prompt must survive it."""
    app, _dispatcher = dispatching_app(raises=ConnectionError("Network error"))

    SyncCliHandler.handle(_args("BTCUSDT"), app)

    assert "❌ Sync failed: Network error" in capsys.readouterr().out


def test_an_interval_argparse_accepts_but_the_domain_rejects_never_dispatches(capsys):
    """`--interval` is declared as a free-form string, so argparse cannot catch
    a value that is not a real timeframe — `TimeFrame()` does, inside the
    handler. This is the one validation that is genuinely the handler's, and it
    is why parsing moving out does not make the handler validation-free."""
    app, dispatcher = dispatching_app()

    SyncCliHandler.handle(_args("BTCUSDT", interval="INVALID"), app)

    assert "❌ Validation Error" in capsys.readouterr().out
    dispatcher.dispatch.assert_not_called()

"""`stream start` / `stream stop` at the prompt, from parsed arguments on.

`EPIC-025` PR 0.4a-2 moved parsing into the shell, so the `-h` case moved to
`tests/unit/presentation/cli/test_interactive_shell.py`. The bare-`stream` case
stayed, because it is not argparse's to answer: `cli_commands.json` declares
the `action` subparser without `required`, so argparse hands back
`action=None` rather than rejecting the line, and deciding what to do with that
is this handler's call.

Unlike `sync`, `stream` reads a response object: both commands return a result
with `.success` and `.message`, so success and a refusal are different printed
outcomes, and a raised exception is a third.
"""

from argparse import Namespace

from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream import (
    StopLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.stream_cli_handler import (
    StreamCliHandler,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.market_data.cli.dispatching_app import (
    dispatching_app,
)


def _start(symbols: str = "BTCUSDT", interval: str = "1m") -> Namespace:
    return Namespace(action="start", symbols=symbols, interval=interval)


def _stop() -> Namespace:
    return Namespace(action="stop")


def test_start_dispatches_one_command_with_upper_cased_symbols(capsys):
    app, dispatcher = dispatching_app()

    StreamCliHandler.handle(_start("ethusdt", "1m"), app)

    dispatcher.dispatch.assert_called_once()
    args, _ = dispatcher.dispatch.call_args
    assert args[0] == StartLiveStreamCommand
    assert args[1].symbols == ["ETHUSDT"]
    assert "✅ Live stream started" in capsys.readouterr().out


def test_start_reports_a_refusal(capsys):
    app, _dispatcher = dispatching_app(success=False, message="Failed")

    StreamCliHandler.handle(_start(), app)

    assert "❌ Failed to start stream: Failed" in capsys.readouterr().out


def test_stop_dispatches_the_stop_command(capsys):
    app, dispatcher = dispatching_app()

    StreamCliHandler.handle(_stop(), app)

    dispatcher.dispatch.assert_called_once()
    assert dispatcher.dispatch.call_args[0][0] == StopLiveStreamCommand
    assert "✅ Live stream stopped" in capsys.readouterr().out


def test_stop_reports_a_refusal(capsys):
    app, _dispatcher = dispatching_app(success=False, message="Error")

    StreamCliHandler.handle(_stop(), app)

    assert "❌ Failed to stop stream" in capsys.readouterr().out


def test_a_raised_start_failure_is_reported_not_propagated(capsys):
    """A real dispatch failure (network, DB) raises out of dispatch() rather
    than returning a success=False result — same class as `sync`'s. The prompt
    must survive it."""
    app, _dispatcher = dispatching_app(raises=ConnectionError("Network error"))

    StreamCliHandler.handle(_start(), app)

    assert "❌ Failed to start stream: Network error" in capsys.readouterr().out


def test_a_raised_stop_failure_is_reported_not_propagated(capsys):
    app, _dispatcher = dispatching_app(raises=ConnectionError("Network error"))

    StreamCliHandler.handle(_stop(), app)

    assert "❌ Failed to stop stream: Network error" in capsys.readouterr().out


def test_a_bare_stream_line_asks_for_an_action_instead_of_crashing(capsys):
    """`action` is an unrequired subparser, so argparse returns `None` for it
    rather than rejecting the line — the handler must not index into it."""
    app, dispatcher = dispatching_app()

    StreamCliHandler.handle(Namespace(action=None), app)

    assert "Usage: stream start" in capsys.readouterr().out
    dispatcher.dispatch.assert_not_called()


def test_an_interval_the_domain_rejects_never_dispatches(capsys):
    app, dispatcher = dispatching_app()

    StreamCliHandler.handle(_start(interval="INVALID"), app)

    assert "❌ Validation Error" in capsys.readouterr().out
    dispatcher.dispatch.assert_not_called()

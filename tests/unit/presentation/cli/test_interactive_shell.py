from argparse import Namespace
from typing import Any
from unittest.mock import Mock, patch

from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    ICliCommandTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.sync_cli_handler import (
    SyncCliHandler,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.interactive_shell import (
    InteractiveShell,
)
from Sagittarius_Elite_Warrior.src.shell.cli_registry import CliRegistry
from Sagittarius_Elite_Warrior.src.shell.modules import MODULES
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig


def _cli_table() -> CliRegistry:
    """The real registry with the real declarations (`EPIC-025` PR 1.3c-5).

    Not a stub: a test that invented `{"sync": SyncCliHandler}` here would
    pass even if `market_data.declare_cli()` stopped declaring anything, which
    is exactly the wiring these tests exist to cover.
    """
    registry = CliRegistry()
    for module_cls in MODULES:
        module_cls().declare_cli(registry)
    return registry


def _shell_app(config: Any, dispatcher: Any = None) -> Mock:
    """An `App` double whose `resolve` routes **by type**.

    The one-answer shape (`resolve.return_value = config`) is what
    `_resolving_app`'s own docstring below warns about: every port gets the
    config mock, so a handler resolving the wrong thing looks plausible and
    fails on a symptom instead of the cause. Ten tests in this file used it
    until PR 1.3c-5 gave them all one builder.
    """
    answers: dict[Any, Any] = {IConfig: config, ICliCommandTable: _cli_table()}
    if dispatcher is not None:
        answers[ICommandDispatcher] = dispatcher

    app = Mock(spec=App)
    app.container.resolve.side_effect = lambda port: answers[port]
    return app


def _resolving_app(config: Mock) -> tuple[Mock, Mock]:
    """An `App` whose container answers **per port**, not one mock for all.

    `EPIC-025` PR 0.4a-2 found out the hard way why this matters. The fixture
    used to point `container.resolve` at a single `IConfig` mock whatever was
    asked for, so when the handler started resolving `ICommandDispatcher`, it
    got that config mock, `.dispatch` did not exist, and the handler's own
    `except Exception` turned a programming error into a friendly
    "Sync failed" on stdout. The test then failed on the *symptom* — dispatch
    never called — with the real cause hidden in captured output.

    Routing by type keeps a wrong resolve loud instead of plausible.
    """
    dispatcher = Mock(spec=ICommandDispatcher)
    response = Mock()
    response.success = True
    dispatcher.dispatch.return_value = response

    return _shell_app(config, dispatcher), dispatcher


def test_interactive_shell_execute_sync():
    config = Mock(spec=IConfig)
    config.get.return_value = {
        "sync": {
            "help": "Synchronize market data from Binance",
            "args": [
                {"name": "--symbols", "type": "str", "required": True},
                {"name": "--interval", "type": "str", "default": "1m"},
                {"name": "--days", "type": "int", "default": 30},
            ],
        }
    }
    app, dispatcher = _resolving_app(config)

    shell = InteractiveShell(app)

    # Directly test the routing via cmd default
    shell.default("sync --symbols ETHUSDT --interval 1m --days 2")

    dispatcher.dispatch.assert_called_once()
    args, _kwargs = dispatcher.dispatch.call_args
    assert args[0] == SyncMarketDataCommand
    cmd = args[1]
    assert cmd.symbols == ["ETHUSDT"]
    assert cmd.days_back_if_empty == 2


def test_interactive_shell_do_exit():
    shell = InteractiveShell(_shell_app(Mock(spec=IConfig)))

    result = shell.do_exit("")
    assert result is True


def test_interactive_shell_do_quit():
    shell = InteractiveShell(_shell_app(Mock(spec=IConfig)))

    result = shell.do_quit("")
    assert result is True


def test_interactive_shell_emptyline():
    shell = InteractiveShell(_shell_app(Mock(spec=IConfig)))

    # Should not raise or repeat
    shell.emptyline()


def test_interactive_shell_default_unknown_cmd(capsys):
    config = Mock(spec=IConfig)
    config.get.return_value = {}
    shell = InteractiveShell(_shell_app(config))

    shell.default("unknown_cmd")
    captured = capsys.readouterr()
    assert "*** Unknown syntax: unknown_cmd" in captured.out


def _sync_only_config() -> Mock:
    """`cli_commands.json`'s declaration for `sync`: one required argument and
    two with defaults. Enough to exercise every branch of `_parse`."""
    config = Mock(spec=IConfig)
    config.get.return_value = {
        "sync": {
            "help": "Synchronize market data from Binance",
            "args": [
                {"name": "--symbols", "type": "str", "required": True},
                {"name": "--interval", "type": "str", "default": "1m"},
                {"name": "--days", "type": "int", "default": 30},
            ],
        }
    }
    return config


def _shell_with_sync() -> tuple[InteractiveShell, Mock]:
    app, dispatcher = _resolving_app(_sync_only_config())
    return InteractiveShell(app), dispatcher


# `EPIC-025` PR 0.4a-2 moved parsing out of each handler and into `default()`,
# so these three cases moved here from `test_sync_cli_handler.py` and
# `test_stream_cli_handler.py`. They were always assertions about argparse
# rather than about syncing or streaming; they now sit next to the code that
# does the parsing, and they are asserted **once** instead of once per command.


def test_a_missing_required_argument_never_reaches_the_handler():
    shell, dispatcher = _shell_with_sync()

    shell.default("sync --interval 1m")

    dispatcher.dispatch.assert_not_called()


def test_dash_h_prints_help_and_never_reaches_the_handler(capsys):
    """argparse answers `-h` by printing and raising `SystemExit`. In a REPL
    that must return to the prompt, not kill the process."""
    shell, dispatcher = _shell_with_sync()

    shell.default("sync -h")

    assert "--symbols" in capsys.readouterr().out
    dispatcher.dispatch.assert_not_called()


def test_an_unknown_flag_is_reported_and_never_reaches_the_handler():
    shell, dispatcher = _shell_with_sync()

    shell.default("sync --symbols BTCUSDT --nonsense 3")

    dispatcher.dispatch.assert_not_called()


def test_the_handler_receives_parsed_arguments_not_a_string():
    """The contract PR 0.4a-2 established: by the time a handler is called, the
    line is an `argparse.Namespace` with defaults applied."""
    shell, _dispatcher = _shell_with_sync()

    with patch.object(SyncCliHandler, "handle") as handle:
        shell.default("sync --symbols BTCUSDT")

    handle.assert_called_once()
    args = handle.call_args[0][0]
    assert isinstance(args, Namespace)
    assert args.symbols == "BTCUSDT"
    assert args.interval == "1m"
    assert args.days == 30


def test_interactive_shell_default_empty(capsys):
    config = Mock(spec=IConfig)
    config.get.return_value = {}
    shell = InteractiveShell(_shell_app(config))

    shell.default("")
    captured = capsys.readouterr()
    assert captured.out == ""


def test_interactive_shell_do_help(capsys):
    config = Mock(spec=IConfig)
    config.get.return_value = {"sync": {"help": "Sync cmd"}}
    shell = InteractiveShell(_shell_app(config))

    shell.do_help("")
    captured = capsys.readouterr()
    assert "Sync cmd" in captured.out
    assert "exit" in captured.out


def test_interactive_shell_do_help_specific(capsys):
    config = Mock(spec=IConfig)
    config.get.return_value = {"sync": {"help": "Sync cmd"}}
    shell = InteractiveShell(_shell_app(config))

    shell.do_help("sync")
    captured = capsys.readouterr()
    assert "Sync cmd" in captured.out


def test_interactive_shell_do_help_unknown(capsys):
    config = Mock(spec=IConfig)
    config.get.return_value = {}
    shell = InteractiveShell(_shell_app(config))

    shell.do_help("unknown")
    captured = capsys.readouterr()
    assert "*** No help on unknown" in captured.out


def test_interactive_shell_lifecycle():
    shell = InteractiveShell(_shell_app(Mock(spec=IConfig)))

    context = Mock()
    context.tasks = Mock()
    mock_task = Mock()
    context.tasks.spawn.return_value = mock_task

    shell.start(context)
    context.tasks.spawn.assert_called_once_with(
        shell._run_loop, name="InteractiveShell"
    )
    assert shell.task == mock_task

    # Wait for exit
    shell.wait_for_exit()
    mock_task.future.result.assert_called_once()

    # Stop
    shell.stop(context)


def test_interactive_shell_wait_for_exit_exception():
    shell = InteractiveShell(_shell_app(Mock(spec=IConfig)))

    context = Mock()
    context.tasks = Mock()
    mock_task = Mock()
    mock_task.future.result.side_effect = Exception("Test Error")
    context.tasks.spawn.return_value = mock_task

    shell.start(context)

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.cli.interactive_shell.logger.exception"
    ) as mock_logger:
        shell.wait_for_exit()
        mock_logger.assert_called_once_with(
            "InteractiveShell task raised during shutdown"
        )


def test_interactive_shell_run_loop_keyboard_interrupt(capsys):
    shell = InteractiveShell(_shell_app(Mock(spec=IConfig)))

    with patch.object(shell, "cmdloop", side_effect=KeyboardInterrupt):
        shell._run_loop()

    captured = capsys.readouterr()
    assert "\nExiting..." in captured.out


def test_interactive_shell_do_help_exit(capsys):
    config = Mock(spec=IConfig)
    config.get.return_value = {}
    shell = InteractiveShell(_shell_app(config))

    shell.do_help("exit")
    captured = capsys.readouterr()
    assert "Exit the interactive shell" in captured.out

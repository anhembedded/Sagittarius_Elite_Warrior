from unittest.mock import Mock, patch

from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.interactive_shell import (
    InteractiveShell,
)
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig


def test_interactive_shell_execute_sync():
    app = Mock(spec=App)

    # Mock config
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
    app.container.resolve.return_value = config

    mock_response = Mock()
    mock_response.success = True
    app.dispatch.return_value = mock_response

    shell = InteractiveShell(app)

    # Directly test the routing via cmd default
    shell.default("sync --symbols ETHUSDT --interval 1m --days 2")

    app.dispatch.assert_called_once()
    args, _kwargs = app.dispatch.call_args
    assert args[0] == SyncMarketDataCommand
    cmd = args[1]
    assert cmd.symbols == ["ETHUSDT"]
    assert cmd.days_back_if_empty == 2


def test_interactive_shell_do_exit():
    app = Mock(spec=App)
    app.container.resolve.return_value = Mock(spec=IConfig)
    shell = InteractiveShell(app)

    result = shell.do_exit("")
    assert result is True


def test_interactive_shell_do_quit():
    app = Mock(spec=App)
    app.container.resolve.return_value = Mock(spec=IConfig)
    shell = InteractiveShell(app)

    result = shell.do_quit("")
    assert result is True


def test_interactive_shell_emptyline():
    app = Mock(spec=App)
    app.container.resolve.return_value = Mock(spec=IConfig)
    shell = InteractiveShell(app)

    # Should not raise or repeat
    shell.emptyline()


def test_interactive_shell_default_unknown_cmd(capsys):
    app = Mock(spec=App)
    config = Mock(spec=IConfig)
    config.get.return_value = {}
    app.container.resolve.return_value = config
    shell = InteractiveShell(app)

    shell.default("unknown_cmd")
    captured = capsys.readouterr()
    assert "*** Unknown syntax: unknown_cmd" in captured.out


def test_interactive_shell_default_empty(capsys):
    app = Mock(spec=App)
    config = Mock(spec=IConfig)
    config.get.return_value = {}
    app.container.resolve.return_value = config
    shell = InteractiveShell(app)

    shell.default("")
    captured = capsys.readouterr()
    assert captured.out == ""


def test_interactive_shell_do_help(capsys):
    app = Mock(spec=App)
    config = Mock(spec=IConfig)
    config.get.return_value = {"sync": {"help": "Sync cmd"}}
    app.container.resolve.return_value = config
    shell = InteractiveShell(app)

    shell.do_help("")
    captured = capsys.readouterr()
    assert "Sync cmd" in captured.out
    assert "exit" in captured.out


def test_interactive_shell_do_help_specific(capsys):
    app = Mock(spec=App)
    config = Mock(spec=IConfig)
    config.get.return_value = {"sync": {"help": "Sync cmd"}}
    app.container.resolve.return_value = config
    shell = InteractiveShell(app)

    shell.do_help("sync")
    captured = capsys.readouterr()
    assert "Sync cmd" in captured.out


def test_interactive_shell_do_help_unknown(capsys):
    app = Mock(spec=App)
    config = Mock(spec=IConfig)
    config.get.return_value = {}
    app.container.resolve.return_value = config
    shell = InteractiveShell(app)

    shell.do_help("unknown")
    captured = capsys.readouterr()
    assert "*** No help on unknown" in captured.out


def test_interactive_shell_lifecycle():
    app = Mock(spec=App)
    app.container.resolve.return_value = Mock(spec=IConfig)
    shell = InteractiveShell(app)

    context = Mock()
    context.tasks = Mock()
    mock_task = Mock()
    context.tasks.spawn.return_value = mock_task

    shell.start(context)
    context.tasks.spawn.assert_called_once_with(shell._run_loop, name="InteractiveShell")
    assert shell.task == mock_task

    # Wait for exit
    shell.wait_for_exit()
    mock_task.future.result.assert_called_once()

    # Stop
    shell.stop(context)


def test_interactive_shell_wait_for_exit_exception():
    app = Mock(spec=App)
    app.container.resolve.return_value = Mock(spec=IConfig)
    shell = InteractiveShell(app)

    context = Mock()
    context.tasks = Mock()
    mock_task = Mock()
    mock_task.future.result.side_effect = Exception("Test Error")
    context.tasks.spawn.return_value = mock_task

    shell.start(context)

    with patch('src.presentation.cli.interactive_shell.logger.exception') as mock_logger:
        shell.wait_for_exit()
        mock_logger.assert_called_once_with("InteractiveShell task raised during shutdown")


def test_interactive_shell_run_loop_keyboard_interrupt(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = Mock(spec=IConfig)
    shell = InteractiveShell(app)

    with patch.object(shell, 'cmdloop', side_effect=KeyboardInterrupt):
        shell._run_loop()

    captured = capsys.readouterr()
    assert "\nExiting..." in captured.out


def test_interactive_shell_do_help_exit(capsys):
    app = Mock(spec=App)
    config = Mock(spec=IConfig)
    config.get.return_value = {}
    app.container.resolve.return_value = config
    shell = InteractiveShell(app)

    shell.do_help("exit")
    captured = capsys.readouterr()
    assert "Exit the interactive shell" in captured.out

from unittest.mock import Mock, patch
from sagittarius_engine import App
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken
from Binace_Bot.src.presentation.cli.menu_service import TerminalMenuService
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand


def test_menu_service_execute_sync():
    app = Mock(spec=App)
    # Setup mock dispatch response
    mock_response = Mock()
    mock_response.success = True
    app.dispatch.return_value = mock_response

    service = TerminalMenuService(app)
    token = CancellationToken()

    # Mock inputs: sync command, then exit
    with patch("builtins.input", side_effect=["sync --symbols ETHUSDT --interval 1m --days 2", "exit"]):
        service._run_loop(token)

    app.dispatch.assert_called_once()
    args, kwargs = app.dispatch.call_args
    assert args[0] == SyncMarketDataCommand
    cmd = args[1]
    assert cmd.symbols == ["ETHUSDT"]
    assert cmd.days_back_if_empty == 2


def test_menu_service_graceful_shutdown_on_interrupt():
    app = Mock(spec=App)
    service = TerminalMenuService(app)
    token = CancellationToken()

    # Simulate KeyboardInterrupt on the first input prompt
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        service._run_loop(token)

    # Should exit loop gracefully without errors
    assert True


def test_menu_service_exit_command():
    app = Mock(spec=App)
    service = TerminalMenuService(app)
    token = CancellationToken()

    # Simulate typing 'quit'
    with patch("builtins.input", side_effect=["quit"]):
        service._run_loop(token)

    # Should exit loop gracefully without errors
    assert True

from unittest.mock import Mock, patch
from sagittarius_engine import App
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken
from Binace_Bot.src.presentation.cli.menu_service import TerminalMenuService


def test_menu_service_routing():
    app = Mock(spec=App)
    service = TerminalMenuService(app)
    token = CancellationToken()

    mock_handler = Mock()
    service.handlers["1"] = mock_handler

    # Mock inputs: select "1" (Sync), press enter to continue, select "4" (Exit)
    with patch("builtins.input", side_effect=["1", "", "4"]):
        service._run_loop(token)

    mock_handler.handle.assert_called_once_with(app)


def test_menu_service_graceful_shutdown_on_interrupt():
    app = Mock(spec=App)
    service = TerminalMenuService(app)
    token = CancellationToken()

    # Simulate KeyboardInterrupt on the first input prompt
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        service._run_loop(token)

    # Should exit loop gracefully without errors
    assert True

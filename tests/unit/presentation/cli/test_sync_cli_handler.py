from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.handlers.sync_cli_handler import (
    SyncCliHandler,
)
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig


def _get_mock_config():
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


def test_sync_cli_handler_success(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()

    mock_response = Mock()
    mock_response.success = True
    app.dispatch.return_value = mock_response

    SyncCliHandler.handle("--symbols ETHUSDT,BTCUSDT --interval 1m --days 2", app)

    app.dispatch.assert_called_once()
    args, _ = app.dispatch.call_args
    assert args[0] == SyncMarketDataCommand
    cmd = args[1]
    assert cmd.symbols == ["ETHUSDT", "BTCUSDT"]
    assert cmd.days_back_if_empty == 2

    captured = capsys.readouterr()
    assert "✅ Sync complete." in captured.out


def test_sync_cli_handler_failure(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()

    mock_response = Mock()
    mock_response.success = False
    mock_response.message = "Network error"
    app.dispatch.return_value = mock_response

    SyncCliHandler.handle("--symbols BTCUSDT", app)

    captured = capsys.readouterr()
    assert "❌ Sync failed: Network error" in captured.out


def test_sync_cli_handler_missing_args(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()

    # --symbols is required, so this will trigger argparse error
    # Because exit_on_error=False, it should print Argument Error or exit
    SyncCliHandler.handle("--interval 1m", app)

    app.dispatch.assert_not_called()


def test_sync_cli_handler_help(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()

    SyncCliHandler.handle("-h", app)
    app.dispatch.assert_not_called()


def test_sync_cli_handler_validation_error(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()

    # Trigger value error by passing invalid interval
    SyncCliHandler.handle("--symbols BTCUSDT --interval INVALID", app)

    captured = capsys.readouterr()
    assert "❌ Validation Error" in captured.out
    app.dispatch.assert_not_called()

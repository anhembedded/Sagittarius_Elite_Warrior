from unittest.mock import Mock, patch
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig
from Binace_Bot.src.presentation.cli.handlers.sync_handler import SyncMenuHandler
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame


def _setup_mock_app():
    app = Mock(spec=App)
    mock_config = Mock(spec=IConfig)
    mock_config.get.side_effect = lambda k, d=None: {
        "DEFAULT_SYMBOLS": ["BTCUSDT", "ETHUSDT"],
        "DEFAULT_INTERVAL": "1m",
        "DEFAULT_SYNC_DAYS": 30,
    }.get(k, d)
    app.container.resolve.return_value = mock_config
    return app


def test_sync_menu_handler_success():
    app = _setup_mock_app()
    handler = SyncMenuHandler()

    # Mock inputs: Symbols, Interval, Days
    with patch("builtins.input", side_effect=["BTCUSDT, ETHUSDT", "1m", "30"]):
        handler.handle(app)

    app.dispatch.assert_called_once()
    args, kwargs = app.dispatch.call_args
    assert args[0] == SyncMarketDataCommand
    cmd = args[1]
    assert cmd.symbols == ["BTCUSDT", "ETHUSDT"]
    assert cmd.interval == TimeFrame("1m")
    assert cmd.days_back_if_empty == 30


def test_sync_menu_handler_empty_symbols():
    app = _setup_mock_app()
    handler = SyncMenuHandler()

    with patch("builtins.input", side_effect=["", "1m", "30"]):
        handler.handle(app)
    app.dispatch.assert_called_once()
    args, kwargs = app.dispatch.call_args
    assert args[0] == SyncMarketDataCommand
    cmd = args[1]
    assert cmd.symbols == ["BTCUSDT", "ETHUSDT"]
    assert cmd.interval == TimeFrame("1m")
    assert cmd.days_back_if_empty == 30


def test_sync_menu_handler_invalid_days():
    app = _setup_mock_app()
    handler = SyncMenuHandler()

    with patch("builtins.input", side_effect=["BTC", "1m", "abc"]):
        handler.handle(app)

    app.dispatch.assert_not_called()


def test_sync_menu_handler_invalid_interval():
    app = _setup_mock_app()
    handler = SyncMenuHandler()

    with patch("builtins.input", side_effect=["BTCUSDT", "1", "30"]):
        handler.handle(app)

    app.dispatch.assert_not_called()

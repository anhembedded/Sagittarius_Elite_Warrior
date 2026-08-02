from unittest.mock import Mock, patch
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig
from Binace_Bot.src.presentation.cli.handlers.stream_handler import (
    StartStreamMenuHandler,
    StopStreamMenuHandler,
)
from Binace_Bot.src.application.use_cases.manage_live_stream import (
    StartLiveStreamCommand,
    StartLiveStreamResponse,
    StopLiveStreamCommand,
    StopLiveStreamResponse,
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame


def _setup_mock_app():
    app = Mock(spec=App)
    mock_config = Mock(spec=IConfig)
    mock_config.get.side_effect = lambda k, d=None: {
        "DEFAULT_SYMBOLS": ["BTCUSDT", "ETHUSDT"],
        "DEFAULT_INTERVAL": "1m",
    }.get(k, d)
    app.container.resolve.return_value = mock_config
    return app


def test_start_stream_menu_handler_success():
    app = _setup_mock_app()
    # Mock dispatch to return a successful response
    app.dispatch.return_value = StartLiveStreamResponse(success=True, message="Success")

    handler = StartStreamMenuHandler()

    with patch("builtins.input", side_effect=["BTCUSDT, ETHUSDT", "1m"]):
        handler.handle(app)

    app.dispatch.assert_called_once()
    args, kwargs = app.dispatch.call_args
    assert args[0] == StartLiveStreamCommand
    cmd = args[1]
    assert cmd.symbols == ["BTCUSDT", "ETHUSDT"]
    assert cmd.interval == TimeFrame("1m")


def test_start_stream_menu_handler_empty_symbols():
    app = _setup_mock_app()
    handler = StartStreamMenuHandler()

    with patch("builtins.input", side_effect=["", "1m"]):
        handler.handle(app)

    app.dispatch.assert_called_once()
    args, kwargs = app.dispatch.call_args
    assert args[0] == StartLiveStreamCommand
    cmd = args[1]
    assert cmd.symbols == ["BTCUSDT", "ETHUSDT"]
    assert cmd.interval == TimeFrame("1m")


def test_stop_stream_menu_handler_success():
    app = _setup_mock_app()
    app.dispatch.return_value = StopLiveStreamResponse(success=True, message="Success")

    handler = StopStreamMenuHandler()
    handler.handle(app)

    app.dispatch.assert_called_once()
    args, kwargs = app.dispatch.call_args
    assert args[0] == StopLiveStreamCommand


def test_start_stream_menu_handler_invalid_interval():
    app = _setup_mock_app()
    handler = StartStreamMenuHandler()

    with patch("builtins.input", side_effect=["BTCUSDT", "1"]):
        handler.handle(app)

    app.dispatch.assert_not_called()

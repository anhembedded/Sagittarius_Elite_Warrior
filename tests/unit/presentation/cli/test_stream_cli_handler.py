from unittest.mock import Mock, patch
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig
from Binace_Bot.src.presentation.cli.handlers.stream_cli_handler import StreamCliHandler
from Binace_Bot.src.application.use_cases.stream.start_live_stream import StartLiveStreamCommand
from Binace_Bot.src.application.use_cases.stream.stop_live_stream import StopLiveStreamCommand


def _get_mock_config():
    config = Mock(spec=IConfig)
    config.get.return_value = {
        "stream": {
            "help": "Stream cmd",
            "subparsers": {
                "dest": "action",
                "commands": {
                    "start": {
                        "help": "Start live stream",
                        "args": [
                            {"name": "--symbols", "type": "str", "required": True},
                            {"name": "--interval", "type": "str", "required": True}
                        ]
                    },
                    "stop": {
                        "help": "Stop live stream"
                    }
                }
            }
        }
    }
    return config

def test_stream_cli_handler_start_success(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()
    
    mock_response = Mock()
    mock_response.success = True
    app.dispatch.return_value = mock_response

    StreamCliHandler.handle("start --symbols ETHUSDT --interval 1m", app)

    app.dispatch.assert_called_once()
    args, _ = app.dispatch.call_args
    assert args[0] == StartLiveStreamCommand
    cmd = args[1]
    assert cmd.symbols == ["ETHUSDT"]
    
    captured = capsys.readouterr()
    assert "✅ Live stream started" in captured.out

def test_stream_cli_handler_start_failure(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()
    
    mock_response = Mock()
    mock_response.success = False
    mock_response.message = "Failed"
    app.dispatch.return_value = mock_response

    StreamCliHandler.handle("start --symbols BTC --interval 1m", app)
    
    captured = capsys.readouterr()
    assert "❌ Failed to start stream: Failed" in captured.out

def test_stream_cli_handler_stop_success(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()
    
    mock_response = Mock()
    mock_response.success = True
    app.dispatch.return_value = mock_response

    StreamCliHandler.handle("stop", app)

    app.dispatch.assert_called_once()
    assert app.dispatch.call_args[0][0] == StopLiveStreamCommand
    
    captured = capsys.readouterr()
    assert "✅ Live stream stopped" in captured.out

def test_stream_cli_handler_stop_failure(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()
    
    mock_response = Mock()
    mock_response.success = False
    mock_response.message = "Error"
    app.dispatch.return_value = mock_response

    StreamCliHandler.handle("stop", app)
    
    captured = capsys.readouterr()
    assert "❌ Failed to stop stream" in captured.out

def test_stream_cli_handler_no_action(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()

    StreamCliHandler.handle("", app)
    
    captured = capsys.readouterr()
    assert "usage:" in captured.out
    app.dispatch.assert_not_called()

def test_stream_cli_handler_help(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()

    StreamCliHandler.handle("-h", app)
    app.dispatch.assert_not_called()

def test_stream_cli_handler_validation_error(capsys):
    app = Mock(spec=App)
    app.container.resolve.return_value = _get_mock_config()
    
    StreamCliHandler.handle("start --symbols BTCUSDT --interval INVALID", app)
    
    captured = capsys.readouterr()
    assert "❌ Validation Error" in captured.out
    app.dispatch.assert_not_called()

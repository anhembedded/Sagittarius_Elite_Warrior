from unittest.mock import Mock, patch
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig
from Binace_Bot.src.presentation.cli.interactive_shell import InteractiveShell
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand


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
                {"name": "--days", "type": "int", "default": 30}
            ]
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
    args, kwargs = app.dispatch.call_args
    assert args[0] == SyncMarketDataCommand
    cmd = args[1]
    assert cmd.symbols == ["ETHUSDT"]
    assert cmd.days_back_if_empty == 2

def test_interactive_shell_do_exit():
    app = Mock(spec=App)
    shell = InteractiveShell(app)

    result = shell.do_exit("")
    assert result is True

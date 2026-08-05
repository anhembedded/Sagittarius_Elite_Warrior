import pytest
from unittest.mock import Mock
from Binace_Bot.src.application.use_cases.backtest.stop_backtest.command import StopBacktestCommand
from Binace_Bot.src.application.use_cases.backtest.stop_backtest.handler import StopBacktestCommandHandler
from Binace_Bot.src.application.use_cases.backtest.run_backtest.handler import BacktestState

def test_stop_backtest_handler():
    # Arrange
    state = BacktestState()
    state.is_running = True
    
    handler = StopBacktestCommandHandler(state)
    command = StopBacktestCommand()
    
    # Act
    handler.execute(command)
    
    # Assert
    assert state.is_running is False

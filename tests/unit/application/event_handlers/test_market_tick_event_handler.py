import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.application.event_handlers.market_data.market_tick_event_handler import MarketTickEventHandler

def test_market_tick_event_handler():
    # Arrange
    logger_mock = Mock()
    app_mock = Mock()
    handler = MarketTickEventHandler(app_mock)
    
    # Inject mock logger for testing
    handler.logger = logger_mock
    
    dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
    market_data = MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=dt,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=dt,
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
    )
    
    event = MarketTickEvent(market_data=market_data)
    
    # Act
    handler.handle(event)
    
    # Assert
    logger_mock.info.assert_called_once()
    call_args = logger_mock.info.call_args[0][0]
    assert "Processing tick for" in call_args
    assert "BTCUSDT" in call_args

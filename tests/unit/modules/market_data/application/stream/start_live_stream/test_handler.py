from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.handler import (
    StartLiveStreamCommandHandler,
)


def test_execute_forwards_owner_market_symbols_and_interval_to_subscribe():
    """`BOT-126` — the handler is the only place translating the command's
    `owner` into the port's `subscribe()` call; a typo/param-order slip here
    would silently scope every subscription wrong."""
    stream_service = Mock()
    stream_service.subscribe.return_value = True
    handler = StartLiveStreamCommandHandler(stream_service)

    response = handler.execute(
        StartLiveStreamCommand(
            owner="trading",
            market_type=MarketType.SPOT,
            symbols=["BTCUSDT"],
            interval=TimeFrame.ONE_MINUTE,
        )
    )

    stream_service.subscribe.assert_called_once_with(
        "trading", MarketType.SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE
    )
    assert response.success is True


def test_execute_reports_failure_when_subscribe_returns_false():
    stream_service = Mock()
    stream_service.subscribe.return_value = False
    handler = StartLiveStreamCommandHandler(stream_service)

    response = handler.execute(
        StartLiveStreamCommand(
            owner="dashboard",
            market_type=MarketType.SPOT,
            symbols=["ETHUSDT"],
            interval=TimeFrame.FIVE_MINUTES,
        )
    )

    assert response.success is False

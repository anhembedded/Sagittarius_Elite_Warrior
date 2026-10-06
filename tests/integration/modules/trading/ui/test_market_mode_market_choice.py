"""`EPIC-033Q` — View → Futures market reloads the open charts from the Futures
store, through the real candle feed the mode builds (`MarketDataCandleFeed`)
over in-memory market-data ports; the Spot candles never come back."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    SHOW_FUTURES,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    MarketPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.watchlist_stream import (
    WATCHLIST_STREAM_OWNER,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.trading.ui.market_mode_fixtures import (
    market_mode,
)

_SPOT_CLOSE = 105.0
_FUTURES_CLOSE = 205.0


@pytest.fixture
def mode(qapp):
    history = FakeHistoricalKlines()
    for market, close in (
        (MarketType.SPOT, _SPOT_CLOSE),
        (MarketType.FUTURES_USD_M, _FUTURES_CLOSE),
    ):
        history.seed(
            [candle("BTCUSDT", minute, close_price=close) for minute in range(30)],
            market,
        )
    with market_mode(history) as built:
        yield built.presenter, built.actions, history, built.stream


def _drawn_closes(presenter: MarketPresenter) -> set[float]:
    card = presenter.charts["BTCUSDT"].chart
    return {close for *_ohlc, close in card._raw_history}


def test_futures_reloads_the_open_chart_from_the_futures_store(mode):
    presenter, registry, history, stream = mode
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    assert _drawn_closes(presenter) == {_SPOT_CLOSE}

    registry.action(SHOW_FUTURES).trigger()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert _drawn_closes(presenter) == {_FUTURES_CLOSE}
    assert history.reads[-1].market is MarketType.FUTURES_USD_M
    for owner in (WATCHLIST_STREAM_OWNER, "market.BTCUSDT"):
        held = stream.held_by(owner)
        assert held is not None
        assert held.market_type is MarketType.FUTURES_USD_M

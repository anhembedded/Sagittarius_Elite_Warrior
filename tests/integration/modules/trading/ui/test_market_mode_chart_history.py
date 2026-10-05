"""`EPIC-033S` — View → Load older candles and View → Load range… against a
seeded in-memory store, through the real candle feed and `ChartHistory` the
mode builds: the first window is the newest 500 candles, the older window
joins it with neither a gap nor a duplicate, and a range draws exactly the
candles that open in it."""

from __future__ import annotations

from datetime import timedelta
from itertools import pairwise

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    T0,
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.chart_history import (
    HistoryRange,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    LOAD_OLDER,
    LOAD_RANGE,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.trading.ui.market_mode_fixtures import (
    market_mode,
)

_MINUTE = timedelta(minutes=1)
#: A first window (500) and a little more than one older window before it.
_STORED = 1_200


@pytest.fixture
def mode(qapp):
    history = FakeHistoricalKlines()
    history.seed([candle("BTCUSDT", minute) for minute in range(_STORED)])
    with market_mode(history) as built:
        built.presenter.on_mode_shown(NavigationSource.RESTORE)
        yield built


def _drawn_opens(mode) -> list[int]:
    chart = mode.presenter.charts["BTCUSDT"]
    return [int((k.open_time - T0) / _MINUTE) for k in chart._klines]


def _drawn_times(mode) -> list[float]:
    card = mode.presenter.charts["BTCUSDT"].chart
    return [t for t, *_ohlc in card._raw_history]


def test_load_older_twice_reaches_back_with_no_gap_and_no_duplicate(mode):
    assert _drawn_opens(mode) == list(range(_STORED - 500, _STORED))

    mode.actions.action(LOAD_OLDER).trigger()
    mode.actions.action(LOAD_OLDER).trigger()

    assert _drawn_opens(mode) == list(range(_STORED))
    times = _drawn_times(mode)
    assert len(times) == _STORED
    assert all(b - a == 60.0 for a, b in pairwise(times))


def test_load_range_draws_exactly_the_candles_that_open_in_it(mode, monkeypatch):
    span = HistoryRange(T0 + 100 * _MINUTE, T0 + 160 * _MINUTE)
    monkeypatch.setattr(
        mode.presenter.view, "ask_history_range", lambda _symbol, _proposed: span
    )

    mode.actions.action(LOAD_RANGE).trigger()

    assert _drawn_opens(mode) == list(range(100, 161))
    assert len(_drawn_times(mode)) == 61
    assert mode.presenter.charts["BTCUSDT"].showing_range

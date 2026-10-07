"""`BOT-167` — a chart's timeframe bar offers only what the market can load.

A real `ChartToolbar` and its picker's `TimeframeSelection`: `1s` is in the
offered grid and (when pinned) in the pill row on Spot, gone on Futures, and
back on Spot. A toolbar that was never told a market offers everything, as
before.
"""

from __future__ import annotations

import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.chart_toolbar import (
    ChartToolbar,
)


def _offered(toolbar: ChartToolbar) -> set[str]:
    return {row.code for group in toolbar._selection.groups for row in group.rows}


def _pinned(toolbar: ChartToolbar) -> set[str]:
    return {row.code for row in toolbar._selection.pinned_rows}


def test_a_toolbar_never_told_a_market_offers_one_second(qapp) -> None:
    assert "1s" in _offered(ChartToolbar())


def test_one_second_disappears_on_futures_and_comes_back_on_spot(qapp) -> None:
    toolbar = ChartToolbar(timeframes=("1s", "1m"), active="1m")
    assert {"1s", "1m"} <= _pinned(toolbar)

    toolbar.set_market(MarketType.FUTURES_USD_M)
    assert "1s" not in _offered(toolbar)
    assert "1s" not in _pinned(toolbar)
    assert toolbar.timeframes.action_for("1s") is None
    assert "1m" in _offered(toolbar)

    toolbar.set_market(MarketType.SPOT)
    assert "1s" in _offered(toolbar)
    assert "1s" in _pinned(toolbar)


def test_the_picker_cannot_choose_one_second_on_futures(qapp) -> None:
    toolbar = ChartToolbar(active="1m")
    toolbar.set_market(MarketType.FUTURES_USD_M)
    seen: list[str] = []
    toolbar.sig_timeframe_changed.connect(seen.append)

    toolbar._selection.choose("1s")

    assert seen == []


def test_switching_to_futures_while_one_second_is_active_falls_back_and_logs(
    qapp, caplog
) -> None:
    toolbar = ChartToolbar(active="1s")
    seen: list[str] = []
    toolbar.sig_timeframe_changed.connect(seen.append)

    with caplog.at_level(logging.INFO, logger="App.ChartToolbar"):
        toolbar.set_market(MarketType.FUTURES_USD_M)

    assert seen == ["1m"]
    assert toolbar._selection.current_code == "1m"
    assert any(
        "1s" in r.getMessage() and "1m" in r.getMessage() for r in caplog.records
    )


def test_a_supported_active_timeframe_is_left_alone(qapp) -> None:
    toolbar = ChartToolbar(active="5m")
    seen: list[str] = []
    toolbar.sig_timeframe_changed.connect(seen.append)

    toolbar.set_market(MarketType.FUTURES_USD_M)

    assert seen == []
    assert toolbar._selection.current_code == "5m"

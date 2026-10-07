"""`BOT-167` — Market mode never offers a timeframe the shown market cannot
load: `1s` is on Spot charts' timeframe bar, gone on Futures, back on Spot."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType


def _offered(presenter, symbol: str = "BTCUSDT") -> set[str]:
    selection = presenter.charts[symbol].chart.toolbar._selection
    return {row.code for group in selection.groups for row in group.rows}


def _shown(build, threads, **overrides):
    presenter = build(**overrides)
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    threads.run_all()
    return presenter


def test_one_second_is_offered_on_spot(build, threads):
    assert "1s" in _offered(_shown(build, threads))


def test_one_second_disappears_on_futures_and_comes_back_on_spot(build, threads):
    presenter = _shown(build, threads)

    presenter.choice._on_chosen(MarketType.FUTURES_USD_M)
    threads.run_all()
    assert "1s" not in _offered(presenter)
    assert "1m" in _offered(presenter)

    presenter.choice._on_chosen(MarketType.SPOT)
    threads.run_all()
    assert "1s" in _offered(presenter)


def test_a_chart_opened_on_futures_with_a_one_second_default_starts_on_one_minute(
    build, threads, caplog
):
    presenter = _shown(build, threads, interval="1s")

    with caplog.at_level(logging.INFO):
        presenter.choice._on_chosen(MarketType.FUTURES_USD_M)
        threads.run_all()

    toolbar = presenter.charts["BTCUSDT"].chart.toolbar
    assert toolbar._selection.current_code == "1m"
    assert presenter.charts["BTCUSDT"]._interval == "1m"
    assert any(
        "1s" in r.getMessage() and "1m" in r.getMessage() for r in caplog.records
    )

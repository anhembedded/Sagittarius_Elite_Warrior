"""`EPIC-040` follow-up — a toolbar a host limits to some timeframes offers only those.

A real `ChartToolbar` with `offered_codes`, as the backtest workbench builds it for its interval: the
pinned actions and the picker's grid hold the subset, a choice outside it is ignored, and a market
narrows the subset further instead of replacing it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.chart_toolbar import (
    ChartToolbar,
)

_SUBSET = ("1s", "1m", "15m", "1h")


def _offered(toolbar: ChartToolbar) -> set[str]:
    return {row.code for group in toolbar._selection.groups for row in group.rows}


def test_only_the_named_timeframes_are_offered_and_pinned(qapp) -> None:
    toolbar = ChartToolbar(timeframes=_SUBSET, active="15m", offered_codes=_SUBSET)

    assert _offered(toolbar) == set(_SUBSET)
    assert [a.text() for a in toolbar.timeframes.timeframe_actions()] == list(_SUBSET)
    assert toolbar.active_timeframe == "15m"


def test_a_timeframe_outside_the_subset_cannot_be_chosen(qapp) -> None:
    toolbar = ChartToolbar(timeframes=_SUBSET, active="15m", offered_codes=_SUBSET)
    seen: list[str] = []
    toolbar.sig_timeframe_changed.connect(seen.append)

    toolbar._selection.choose("1d")
    toolbar._selection.choose("1h")

    assert seen == ["1h"]
    assert toolbar.active_timeframe == "1h"


def test_a_market_narrows_the_subset_and_does_not_replace_it(qapp) -> None:
    toolbar = ChartToolbar(timeframes=_SUBSET, active="15m", offered_codes=_SUBSET)

    toolbar.set_market(MarketType.FUTURES_USD_M)

    assert _offered(toolbar) == {"1m", "15m", "1h"}


def test_a_toolbar_given_no_subset_offers_every_timeframe_as_before(qapp) -> None:
    toolbar = ChartToolbar(active="15m")

    assert {"1d", "1s", "15m"} <= _offered(toolbar)


def test_the_fallback_after_a_market_change_stays_inside_the_subset(qapp) -> None:
    """`1s` is not loadable on Futures; the nearest timeframe the market loads is `1m`, which this
    host did not offer, so the toolbar moves to the nearest one it did."""
    toolbar = ChartToolbar(
        timeframes=("1s", "15m", "1h"), active="1s", offered_codes=("1s", "15m", "1h")
    )
    seen: list[str] = []
    toolbar.sig_timeframe_changed.connect(seen.append)

    toolbar.set_market(MarketType.FUTURES_USD_M)

    assert seen == ["15m"]
    assert toolbar.active_timeframe == "15m"


def test_a_toolbar_that_hides_its_timeframes_shows_none_of_them(qapp) -> None:
    """`EPIC-040` F3: the row and its "More timeframes…" go, and stay gone when the pins change."""
    toolbar = ChartToolbar(timeframes=_SUBSET, active="15m", offered_codes=_SUBSET)

    toolbar.hide_timeframes()
    toolbar._selection.toggle_pinned("1s")

    shown = [action.text() for action in toolbar.actions() if action.isVisible()]
    assert shown == []
    assert toolbar.timeframes.more_action in toolbar.actions()


def test_a_toolbar_shows_its_timeframes_unless_asked_not_to(qapp) -> None:
    toolbar = ChartToolbar(timeframes=_SUBSET, active="15m", offered_codes=_SUBSET)

    shown = [action.text() for action in toolbar.actions() if action.isVisible()]

    assert shown[: len(_SUBSET)] == list(_SUBSET)
    assert toolbar.timeframes.more_action.text() in shown

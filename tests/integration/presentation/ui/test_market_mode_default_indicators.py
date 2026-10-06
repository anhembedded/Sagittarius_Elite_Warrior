"""US-07 and `BOT-032` Phase 6 in the composed app: the Market mode opens with
the four EMAs drawn and RSI and MACD offered but off, each script on its own
row of the chart (an overlay on the price, or a subplot of its own) under its
own key.

@details Re-homed from the Dev Board's indicator tests (TC-IND-01, -02, -04)
when the Dev Board was deleted (`EPIC-033P` stage 3): the Market mode owns
the live chart and its Indicators list now. The scripts are the ones
`create_app()` registers, not a test's own registry, so a script that loses
its `default_enabled` or its `overlay` fails here. What one script computes
is `tests/unit/support/indicators/indicator_scripts/`'s; that a checked
script reaches every open chart is `test_market_presenter.py`'s.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    MarketPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_view import (
    MarketView,
)

_DEFAULT_EMAS = {"ema_20", "ema_50", "ema_100", "ema_200"}
_WAIT_MS = 5_000


def _market(navigate) -> tuple[MarketPresenter, MarketView]:
    entry = navigate(MARKET_ROUTE)
    presenter, view = entry["presenter_instance"], entry["view_instance"]
    assert isinstance(presenter, MarketPresenter)
    assert isinstance(view, MarketView)
    return presenter, view


def _checked_keys(view: MarketView) -> set[str]:
    items = (view.indicators.item(row) for row in range(view.indicators.count()))
    return {
        item.data(Qt.ItemDataRole.UserRole)
        for item in items
        if item.checkState() == Qt.CheckState.Checked
    }


def _offered_keys(view: MarketView) -> set[str]:
    return {
        view.indicators.item(row).data(Qt.ItemDataRole.UserRole)
        for row in range(view.indicators.count())
    }


def test_the_four_emas_are_checked_and_rsi_and_macd_are_offered_but_off(
    qtbot, main_window, navigate
):
    """US-07: "no indicator hardcoded in the engine, default is EMA
    200/100/50/20"; RSI and MACD stay opt-in, like every other script."""
    qtbot.addWidget(main_window)
    _presenter, view = _market(navigate)

    assert {"rsi_14", "macd_full"} <= _offered_keys(view)
    assert _checked_keys(view) == _DEFAULT_EMAS


def test_the_first_chart_draws_the_four_emas_on_the_price(qtbot, main_window, navigate):
    """TC-IND-02: an EMA is drawn on the price plot, not a row of its own."""
    qtbot.addWidget(main_window)
    presenter, _view = _market(navigate)
    qtbot.waitUntil(lambda: bool(presenter.charts), timeout=_WAIT_MS)
    chart = next(iter(presenter.charts.values()))

    qtbot.waitUntil(
        lambda: set(chart._runner.active) == _DEFAULT_EMAS, timeout=_WAIT_MS
    )
    active = chart._runner.active
    assert all(active[key].overlay for key in _DEFAULT_EMAS)


def test_rsi_and_macd_checked_with_the_emas_each_keep_their_own_key(
    qtbot, main_window, navigate
):
    """TC-IND-01 and -04: RSI and MACD are subplots, and with the four EMAs
    all six are drawn under their own keys, none overwriting another."""
    qtbot.addWidget(main_window)
    presenter, view = _market(navigate)
    qtbot.waitUntil(lambda: bool(presenter.charts), timeout=_WAIT_MS)
    wanted = _DEFAULT_EMAS | {"rsi_14", "macd_full"}

    view.indicators_changed.emit(tuple(sorted(wanted)))

    chart = next(iter(presenter.charts.values()))
    qtbot.waitUntil(lambda: set(chart._runner.active) == wanted, timeout=_WAIT_MS)
    active = chart._runner.active
    assert active["rsi_14"].overlay is False
    assert active["macd_full"].overlay is False
    assert all(active[key].overlay for key in _DEFAULT_EMAS)

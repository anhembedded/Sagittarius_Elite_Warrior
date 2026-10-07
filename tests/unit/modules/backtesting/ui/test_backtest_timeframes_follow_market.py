"""`BOT-167` — the Backtest screen offers no timeframe its market cannot load.

Futures has no 1-second klines, so while the screen's market is Futures `1s`
is absent from the run setup's timeframe field and from every chart's
timeframe bar, and a switch to Futures while `1s` is selected falls back to a
valid timeframe and logs it. Spot keeps `1s`.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QComboBox
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.coordinators.market_selection_coordinator import (
    MarketSelectionCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.run_setup_panel import (
    RunSetupPanel,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.backtesting.ui.coordinators.conftest import (
    InMemoryScreenState,
)

_SPOT = MarketType.SPOT.value
_FUTURES = MarketType.FUTURES_USD_M.value


def _codes(combo: QComboBox) -> list[object]:
    return [combo.itemData(i) for i in range(combo.count())]


def test_the_view_model_offers_one_second_on_spot_only(qapp):
    view_model = BackTestViewModel()

    view_model.broker_sim.market = _SPOT
    assert "1s" in view_model.timeframeOptions

    view_model.broker_sim.market = _FUTURES
    assert "1s" not in view_model.timeframeOptions
    assert "1m" in view_model.timeframeOptions


def test_the_run_setup_timeframe_field_follows_the_market(qapp):
    view_model = BackTestViewModel()
    view_model.broker_sim.market = _SPOT
    panel = RunSetupPanel(view_model)
    assert "1s" in _codes(panel.timeframe)

    view_model.broker_sim.market = _FUTURES
    assert "1s" not in _codes(panel.timeframe)

    view_model.broker_sim.market = _SPOT
    assert "1s" in _codes(panel.timeframe)


def _coordinator(
    market: MarketType, timeframe: list[str]
) -> MarketSelectionCoordinator:
    return MarketSelectionCoordinator(
        state=InMemoryScreenState(market=market),
        set_symbol_options_market=lambda _market: None,
        refresh_market_rule_verification=lambda: None,
        notify_config_changed=lambda: None,
        request_chart_preview=lambda: None,
        get_timeframe=lambda: timeframe[0],
        set_timeframe=lambda value: timeframe.__setitem__(0, value),
    )


def test_a_switch_to_futures_with_one_second_selected_falls_back_and_logs(caplog):
    timeframe = ["1s"]

    with caplog.at_level(logging.INFO, logger="App.BackTestPresenter"):
        _coordinator(MarketType.FUTURES_USD_M, timeframe).on_market_changed()

    assert timeframe == ["1m"]
    assert any(
        "1s" in r.getMessage() and "1m" in r.getMessage() for r in caplog.records
    )


def test_a_switch_keeps_a_timeframe_the_market_loads():
    timeframe = ["1s"]
    _coordinator(MarketType.SPOT, timeframe).on_market_changed()
    assert timeframe == ["1s"]

    timeframe = ["5m"]
    _coordinator(MarketType.FUTURES_USD_M, timeframe).on_market_changed()
    assert timeframe == ["5m"]


def _offered(host) -> set[str]:
    selection = host.chart_card.toolbar._selection
    return {row.code for group in selection.groups for row in group.rows}


def test_every_chart_bar_follows_the_market_including_cards_made_later(qapp, request):
    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    view_model = BackTestViewModel()
    view_model.broker_sim.market = _SPOT
    view.set_view_model(view_model)

    first = view.render_symbol_cards(["BTCUSDT"])
    assert "1s" in _offered(first[0])

    view_model.broker_sim.market = _FUTURES
    assert "1s" not in _offered(first[0])

    rebuilt = view.render_symbol_cards(["ETHUSDT"])
    assert "1s" not in _offered(rebuilt[0])

    view_model.broker_sim.market = _SPOT
    assert "1s" in _offered(rebuilt[0])

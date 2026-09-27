"""EPIC-027D — the Backtest screen chooses Spot or Futures (USDⓈ-M) and shows
only what that market can do: the selector, the hidden leverage section, and
the short-only filters a Spot screen does not offer."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QWidget
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals.strategy_properties_dialog import (
    StrategyPropertiesDialog,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_top_panel import (
    BackTestTopPanel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_trade_logs_panel import (
    BackTestTradeLogsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.coordinators.market_selection_coordinator import (
    MarketSelectionCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_canvas_view import (
    MarkerSideFilter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_controls import (
    BacktestChartControls,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.market_selector import (
    MarketSelector,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.broker_sim_view_model import (
    BrokerSimViewModel,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.backtesting.ui.coordinators.conftest import (
    InMemoryScreenState,
)

_SPOT = MarketType.SPOT.value
_FUTURES = MarketType.FUTURES_USD_M.value


def test_the_selector_offers_spot_and_usd_m_futures_only(qapp):
    selector = MarketSelector(BrokerSimViewModel())

    assert selector.objectName() == "comboBacktestMarket"
    assert [selector.itemData(i) for i in range(selector.count())] == [
        _FUTURES,
        _SPOT,
    ]
    assert selector.currentData() == _FUTURES


def test_a_pick_writes_the_view_model_and_a_view_model_change_moves_the_pick(qapp):
    broker_sim = BrokerSimViewModel()
    selector = MarketSelector(broker_sim)

    selector.setCurrentIndex(selector.findData(_SPOT))
    assert broker_sim.market == _SPOT

    broker_sim.market = _FUTURES  # a restored screen state, say
    assert selector.currentData() == _FUTURES


def test_the_top_panel_places_the_selector_in_the_toolbar(qapp):
    panel = BackTestTopPanel(BackTestViewModel())

    assert panel.findChild(QComboBox, "comboBacktestMarket") is not None


def test_the_leverage_section_is_hidden_not_disabled_in_spot(qapp):
    view_model = BackTestViewModel()
    dialog = StrategyPropertiesDialog(view_model)
    section = dialog.findChild(QWidget, "leverageSection")

    assert section is not None
    assert not section.isHidden()

    view_model.broker_sim.market = _SPOT
    assert section.isHidden()

    view_model.broker_sim.market = _FUTURES
    assert not section.isHidden()


def test_a_spot_screen_offers_no_short_trade_log_tab_and_falls_back_to_all(qapp):
    view_model = BackTestViewModel()
    panel = BackTestTradeLogsPanel(view_model)
    short_tab = panel.findChild(QWidget, "tabTradeLogFilter_short")
    view_model.trade_log.filter = "short"

    view_model.broker_sim.market = _SPOT

    assert short_tab.isHidden()
    assert view_model.trade_log.filter == "all"

    view_model.broker_sim.market = _FUTURES
    assert not short_tab.isHidden()


def _side_options(controls: BacktestChartControls) -> list[object]:
    combo = controls.findChild(QComboBox, "cboMarkerSideFilter")
    return [combo.itemData(i) for i in range(combo.count())]


def test_the_chart_offers_no_short_only_marker_filter_in_spot(qapp):
    controls = BacktestChartControls()
    combo = controls.findChild(QComboBox, "cboMarkerSideFilter")
    combo.setCurrentIndex(combo.findData(MarkerSideFilter.SHORT_ONLY))

    controls.show_sides_for(MarketType.SPOT)

    assert MarkerSideFilter.SHORT_ONLY not in _side_options(controls)
    assert controls.side_filter() is MarkerSideFilter.ALL

    controls.show_sides_for(MarketType.FUTURES_USD_M)
    assert MarkerSideFilter.SHORT_ONLY in _side_options(controls)


def test_a_market_switch_repoints_the_catalog_rule_check_config_and_preview():
    calls: list[object] = []
    coordinator = MarketSelectionCoordinator(
        state=InMemoryScreenState(market=MarketType.SPOT),
        set_symbol_options_market=calls.append,
        refresh_market_rule_verification=lambda: calls.append("rule_check"),
        notify_config_changed=lambda: calls.append("config"),
        request_chart_preview=lambda: calls.append("preview"),
    )

    coordinator.on_market_changed()

    assert calls == [MarketType.SPOT, "rule_check", "config", "preview"]

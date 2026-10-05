"""`EPIC-027D` — the Backtest toolbar's Spot / Futures (USDⓈ-M) choice."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QWidget

from .logic.backtest_market import BACKTEST_MARKETS, market_label
from .view_models.broker_sim_view_model import BrokerSimViewModel


class MarketSelector(QComboBox):
    """
    @brief A plain `QComboBox` (`ui-presentation-rule.md` §1: standard parts),
    bound both ways to `BrokerSimViewModel.market`.
    @details The ViewModel is the single writer: a pick writes `market`, and
    `marketChanged` — whether from a pick, a restored screen state or a
    history replay — moves the selection back. No `setStyleSheet()`: the
    styling ratchet (`test_app_styling_only_shrinks.py`) only shrinks, and the
    OS theme styles a combo already. The orphaned `MarketPickerDialog`
    (`presentation/ui/components/market_picker/`) is not used: it offers
    COIN-M, which the engine refuses (ADR D1), and a toolbar combo needs no
    second picker pattern.
    """

    def __init__(
        self, broker_sim: BrokerSimViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("comboBacktestMarket")
        self.setToolTip(
            "Which market this backtest simulates: its candles, symbols and "
            "exchange rules"
        )
        for market in BACKTEST_MARKETS:
            self.addItem(market_label(market), market.value)
        self._broker_sim = broker_sim
        self._show_view_model_market()
        self.currentIndexChanged.connect(self._on_index_changed)
        broker_sim.marketChanged.connect(self._show_view_model_market)

    def _on_index_changed(self, index: int) -> None:
        value = self.itemData(index)
        if isinstance(value, str):
            self._broker_sim.set_market(value)

    def _show_view_model_market(self) -> None:
        index = self.findData(self._broker_sim.market)
        if index < 0 or index == self.currentIndex():
            return
        self.blockSignals(True)
        self.setCurrentIndex(index)
        self.blockSignals(False)

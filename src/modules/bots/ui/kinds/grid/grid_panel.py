"""`EPIC-029F` — the Grid's parameter editor.

Every parameter is a field the user owns (the user's rule, 2026-10-03: the
parameters are the user's; the bot judges them, never fixes them). The two
suggestion buttons are the one exception to "never fills a field", and only
on a click: they copy the planner's ATR or Bollinger range into the range
fields, rounded to the symbol's tick, and the user may change them again.

The fields read and write the definition's strings (`GridParams.to_config`
spells them): an exit is `off`, `price:<p>` or `percent:<n>`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
    SuggestedRange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    ExitKind,
    GridSpacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)

#: Binance's own floor for a Spot grid; the planner refuses fewer anyway.
_MIN_GRIDS = 2
_MAX_GRIDS = 1000
#: What a new Grid's count field starts at; the user changes it.
_DEFAULT_GRIDS = 10
_NO_RANGE_YET = "The planner has no {name} range: it needs more stored daily candles."


class _ExitField(QWidget):
    """An exit rule: off, a price, or a percentage beyond the range edge."""

    edited = Signal()

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = QComboBox()
        self.kind.setObjectName(f"cmbGrid{name}Kind")
        for kind in ExitKind:
            self.kind.addItem(kind.value, kind.value)
        self.value = QLineEdit()
        self.value.setObjectName(f"editGrid{name}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.kind)
        layout.addWidget(self.value, 1)
        self.kind.activated.connect(self._on_kind)
        self.value.textEdited.connect(self.edited)

    def encode(self) -> str:
        kind = self._kind()
        if kind is ExitKind.OFF:
            return ExitKind.OFF.value
        return f"{kind.value}:{self.value.text().strip()}"

    def show_encoded(self, text: str) -> None:
        kind_text, _, value = text.partition(":")
        index = self.kind.findText(kind_text.strip())
        self.kind.setCurrentIndex(max(index, 0))
        self.value.setText(value.strip())
        self._sync_value_enabled()

    def _on_kind(self) -> None:
        self._sync_value_enabled()
        self.edited.emit()

    def _sync_value_enabled(self) -> None:
        self.value.setEnabled(self._kind() is not ExitKind.OFF)

    def _kind(self) -> ExitKind:
        """A combo hands a `str` enum back as a plain `str`: data is the value."""
        return ExitKind(self.kind.currentData())


class GridPanel(BotKindPanel):
    """@brief Edits one Grid's parameters."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._market: PlannerMarket | None = None
        self.lower_price = _decimal_field("editGridLower")
        self.upper_price = _decimal_field("editGridUpper")
        self.grid_count = QSpinBox()
        self.grid_count.setObjectName("spinGridCount")
        self.grid_count.setRange(_MIN_GRIDS, _MAX_GRIDS)
        self.grid_count.setValue(_DEFAULT_GRIDS)
        self.spacing = QComboBox()
        self.spacing.setObjectName("cmbGridSpacing")
        for spacing in GridSpacing:
            self.spacing.addItem(spacing.value.capitalize(), spacing.value)
        self.capital = _decimal_field("editGridCapital")
        self.stop_loss = _ExitField("StopLoss")
        self.take_profit = _ExitField("TakeProfit")
        self.suggest_atr = QPushButton("Suggest from ATR")
        self.suggest_atr.setObjectName("btnSuggestAtr")
        self.suggest_bollinger = QPushButton("Suggest from Bollinger")
        self.suggest_bollinger.setObjectName("btnSuggestBollinger")
        self._build_field_layout()
        self._connect()
        self.set_planner_market(None)

    # -- BotKindPanel ----------------------------------------------------- #

    def set_config(self, config: Mapping[str, str]) -> None:
        """Programmatic writes emit nothing: every signal used below is a
        user-edit signal (`textEdited`, `activated`, `editingFinished`)."""
        self.lower_price.setText(config.get("lower", ""))
        self.upper_price.setText(config.get("upper", ""))
        self.grid_count.setValue(_int_or(config.get("grid_count", ""), _DEFAULT_GRIDS))
        index = self.spacing.findData(
            config.get("spacing", GridSpacing.ARITHMETIC.value)
        )
        self.spacing.setCurrentIndex(max(index, 0))
        self.capital.setText(config.get("capital_quote", ""))
        self.stop_loss.show_encoded(config.get("stop_loss", ExitKind.OFF.value))
        self.take_profit.show_encoded(config.get("take_profit", ExitKind.OFF.value))

    def config(self) -> dict[str, str]:
        return {
            "lower": self.lower_price.text().strip(),
            "upper": self.upper_price.text().strip(),
            "grid_count": str(self.grid_count.value()),
            "spacing": GridSpacing(self.spacing.currentData()).value,
            "capital_quote": self.capital.text().strip(),
            "stop_loss": self.stop_loss.encode(),
            "take_profit": self.take_profit.encode(),
        }

    def set_planner_market(self, market: PlannerMarket | None) -> None:
        self._market = market
        _offer(self.suggest_atr, market.atr_range if market else None, "ATR")
        _offer(
            self.suggest_bollinger, market.bollinger if market else None, "Bollinger"
        )

    def set_editable(self, editable: bool) -> None:
        for field in (
            self.lower_price,
            self.upper_price,
            self.grid_count,
            self.spacing,
            self.capital,
            self.stop_loss,
            self.take_profit,
        ):
            field.setEnabled(editable)
        if editable:
            self.set_planner_market(self._market)
        else:
            self.suggest_atr.setEnabled(False)
            self.suggest_bollinger.setEnabled(False)

    # -- internals -------------------------------------------------------- #

    def _build_field_layout(self) -> None:
        form = QFormLayout()
        form.addRow("Lower price", self.lower_price)
        form.addRow("Upper price", self.upper_price)
        form.addRow("Grids", self.grid_count)
        form.addRow("Spacing", self.spacing)
        form.addRow("Capital (quote)", self.capital)
        form.addRow("Stop loss", self.stop_loss)
        form.addRow("Take profit", self.take_profit)
        suggestions = QHBoxLayout()
        suggestions.addWidget(self.suggest_atr)
        suggestions.addWidget(self.suggest_bollinger)
        suggestions.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)
        layout.addLayout(suggestions)

    def _connect(self) -> None:
        for field in (self.lower_price, self.upper_price, self.capital):
            field.textEdited.connect(self._emit)
        self.grid_count.editingFinished.connect(self._emit)
        self.grid_count.lineEdit().textEdited.connect(self._emit)
        self.spacing.activated.connect(self._emit)
        self.stop_loss.edited.connect(self._emit)
        self.take_profit.edited.connect(self._emit)
        self.suggest_atr.clicked.connect(lambda: self._fill_range(self._atr()))
        self.suggest_bollinger.clicked.connect(
            lambda: self._fill_range(self._bollinger())
        )

    def _atr(self) -> SuggestedRange | None:
        return self._market.atr_range if self._market else None

    def _bollinger(self) -> SuggestedRange | None:
        return self._market.bollinger if self._market else None

    def _fill_range(self, suggested: SuggestedRange | None) -> None:
        if suggested is None:
            return
        tick = (
            self._market.terms.tick_size
            if self._market and self._market.terms
            else None
        )
        self.lower_price.setText(str(_to_tick(suggested.lower, tick)))
        self.upper_price.setText(str(_to_tick(suggested.upper, tick)))
        self._emit()

    def _emit(self, *_args: object) -> None:
        self.config_changed.emit(self.config())


def _decimal_field(name: str) -> QLineEdit:
    field = QLineEdit()
    field.setObjectName(name)
    return field


def _offer(button: QPushButton, suggested: SuggestedRange | None, name: str) -> None:
    button.setEnabled(suggested is not None)
    if suggested is None:
        button.setToolTip(_NO_RANGE_YET.format(name=name))
    else:
        button.setToolTip(f"Fill the range with {suggested.lower} – {suggested.upper}.")


def _to_tick(price: Decimal, tick: Decimal | None) -> Decimal:
    if tick is None or tick <= 0:
        return price
    return (price / tick).quantize(Decimal(1), rounding=ROUND_HALF_UP) * tick


def _int_or(text: str, default: int) -> int:
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError):
        return default

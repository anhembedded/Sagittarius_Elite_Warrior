"""`EPIC-003F4` — the Backtest screen's broker-simulation and position-sizing
state (`BOT-104`), lifted out of `BackTestViewModel`.

@details Fourth slice of `EPIC-003F`, under the same rule as `003F1`–`003F3`:
this class owns the state, `BackTestViewModel` forwards to it, and **no
call site changes**. The proof that the forward is faithful is that
`tests/` needs no edit at all.

@par Why these twelve belong together
They are exactly the fields `_build_run_config()` reads to construct one
`PositionSizing` and one `BrokerSimulationConfig` — the answer to *what
would this trade have cost*. `logic/broker_properties_schema.py` already
treats them as one form; this is the state behind that form.

@par The clamps stay with the state, not with the form
`pyramiding >= 1`, `commissionValue >= 0`, `slippageTicks >= 0`,
`leverage >= 1`: a clamp enforced only in the dialog is a clamp that a
restored session state or a Presenter write can walk straight past. They
are here, on the single writer, for the same reason `LiveStrategyConfig`
validates in `__post_init__` rather than in the Trading screen's card.

@par `*Text` vs `*Value` is deliberate, not duplication
`orderSizeText`/`commissionText` hold exactly what the user typed —
including a half-typed `"0."` that `float()` rejects — while
`orderSizeValue`/`commissionValue` hold the last parse that succeeded.
Collapsing them would either reject keystrokes mid-word or feed a run a
number nobody typed.
"""

from __future__ import annotations

from contextlib import suppress

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.commission_type import (
    CommissionType,
)

#: `BOT-041`'s own defaults, unchanged by this move — a fresh app must
#: behave exactly as it did before the state had its own class.
DEFAULT_ORDER_SIZE_VALUE = 100.0
DEFAULT_ORDER_SIZE_TEXT = "100"
DEFAULT_PYRAMIDING = 1
DEFAULT_COMMISSION_VALUE = 0.1
DEFAULT_COMMISSION_TEXT = "0.1"
DEFAULT_SLIPPAGE_TICKS = 0
DEFAULT_LEVERAGE = 1.0
DEFAULT_TAKE_PROFIT_PCT_TEXT = "2.0"

#: Floors the setters enforce. Named rather than inlined so the test that
#: proves the clamp reads the same number the clamp uses.
MIN_PYRAMIDING = 1
MIN_COMMISSION_VALUE = 0.0
MIN_SLIPPAGE_TICKS = 0
MIN_LEVERAGE = 1.0
#: `EPIC-027D` — a fresh screen simulates USD-M Futures, the same default as
#: `BrokerSimulationConfig.market_type`, so a run's semantics do not change
#: for a user who never opens the selector.
DEFAULT_MARKET_TYPE = MarketType.FUTURES_USD_M
DEFAULT_MARKET = DEFAULT_MARKET_TYPE.value
#: Spot trades its own cash: leverage is pinned here (ADR D3).
SPOT_LEVERAGE = 1.0


class BrokerSimViewModel(QObject):
    """@brief What a simulated fill costs, and how big it is."""

    orderSizeTypeChanged = Signal()
    orderSizeValueChanged = Signal()
    orderSizeTextChanged = Signal()
    pyramidingChanged = Signal()
    commissionTypeChanged = Signal()
    commissionValueChanged = Signal()
    commissionTextChanged = Signal()
    slippageTicksChanged = Signal()
    longLeverageChanged = Signal()
    shortLeverageChanged = Signal()
    takeProfitPctEnabledChanged = Signal()
    takeProfitPctTextChanged = Signal()
    marketChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._order_size_type = PositionSizingType.PERCENT_OF_EQUITY.value
        self._order_size_value = DEFAULT_ORDER_SIZE_VALUE
        self._order_size_text = DEFAULT_ORDER_SIZE_TEXT
        self._pyramiding = DEFAULT_PYRAMIDING
        self._commission_type = CommissionType.PERCENT.value
        self._commission_value = DEFAULT_COMMISSION_VALUE
        self._commission_text = DEFAULT_COMMISSION_TEXT
        self._slippage_ticks = DEFAULT_SLIPPAGE_TICKS
        self._long_leverage = DEFAULT_LEVERAGE
        self._short_leverage = DEFAULT_LEVERAGE
        #: `EPIC-001A` — `BrokerSimulationConfig.take_profit_pct` had no UI
        #: path at all before this (only ever set in tests); off until the
        #: user opts in, so a fresh app still behaves exactly as before the
        #: field existed.
        self._take_profit_pct_enabled = False
        self._take_profit_pct_text = DEFAULT_TAKE_PROFIT_PCT_TEXT
        self._market = DEFAULT_MARKET

    # ------------------------------------------------------------------ #
    # Position sizing
    # ------------------------------------------------------------------ #

    def _set_order_size_type(self, value: str) -> None:
        if value != self._order_size_type:
            self._order_size_type = value
            self.orderSizeTypeChanged.emit()

    @property
    def orderSizeType(self) -> str:
        return self._order_size_type

    @orderSizeType.setter
    def orderSizeType(self, value: str) -> None:
        self._set_order_size_type(value)

    def _set_order_size_value(self, value: float) -> None:
        if value != self._order_size_value:
            self._order_size_value = value
            self.orderSizeValueChanged.emit()

    @property
    def orderSizeValue(self) -> float:
        return self._order_size_value

    @orderSizeValue.setter
    def orderSizeValue(self, value: float) -> None:
        self._set_order_size_value(value)

    def _set_order_size_text(self, value: str) -> None:
        if value != self._order_size_text:
            self._order_size_text = value
            with suppress(ValueError):
                self._order_size_value = float(value)
            self.orderSizeTextChanged.emit()
            self.orderSizeValueChanged.emit()

    @property
    def orderSizeText(self) -> str:
        return self._order_size_text

    @orderSizeText.setter
    def orderSizeText(self, value: str) -> None:
        self._set_order_size_text(value)

    def _set_pyramiding(self, value: int) -> None:
        if value != self._pyramiding:
            self._pyramiding = max(MIN_PYRAMIDING, value)
            self.pyramidingChanged.emit()

    @property
    def pyramiding(self) -> int:
        return self._pyramiding

    @pyramiding.setter
    def pyramiding(self, value: int) -> None:
        self._set_pyramiding(value)

    # ------------------------------------------------------------------ #
    # Costs
    # ------------------------------------------------------------------ #

    def _set_commission_type(self, value: str) -> None:
        if value != self._commission_type:
            self._commission_type = value
            self.commissionTypeChanged.emit()

    @property
    def commissionType(self) -> str:
        return self._commission_type

    @commissionType.setter
    def commissionType(self, value: str) -> None:
        self._set_commission_type(value)

    def _set_commission_value(self, value: float) -> None:
        if value != self._commission_value:
            self._commission_value = max(MIN_COMMISSION_VALUE, value)
            self.commissionValueChanged.emit()

    @property
    def commissionValue(self) -> float:
        return self._commission_value

    @commissionValue.setter
    def commissionValue(self, value: float) -> None:
        self._set_commission_value(value)

    def _set_commission_text(self, value: str) -> None:
        if value != self._commission_text:
            self._commission_text = value
            with suppress(ValueError):
                self._commission_value = float(value)
            self.commissionTextChanged.emit()
            self.commissionValueChanged.emit()

    @property
    def commissionText(self) -> str:
        return self._commission_text

    @commissionText.setter
    def commissionText(self, value: str) -> None:
        self._set_commission_text(value)

    def _set_slippage_ticks(self, value: int) -> None:
        if value != self._slippage_ticks:
            self._slippage_ticks = max(MIN_SLIPPAGE_TICKS, value)
            self.slippageTicksChanged.emit()

    @property
    def slippageTicks(self) -> int:
        return self._slippage_ticks

    @slippageTicks.setter
    def slippageTicks(self, value: int) -> None:
        self._set_slippage_ticks(value)

    # ------------------------------------------------------------------ #
    # Leverage and take-profit
    # ------------------------------------------------------------------ #

    def _set_long_leverage(self, value: float) -> None:
        value = self._leverage_allowed(value)
        if value != self._long_leverage:
            self._long_leverage = value
            self.longLeverageChanged.emit()

    @property
    def longLeverage(self) -> float:
        return self._long_leverage

    @longLeverage.setter
    def longLeverage(self, value: float) -> None:
        self._set_long_leverage(value)

    def _set_short_leverage(self, value: float) -> None:
        value = self._leverage_allowed(value)
        if value != self._short_leverage:
            self._short_leverage = value
            self.shortLeverageChanged.emit()

    @property
    def shortLeverage(self) -> float:
        return self._short_leverage

    @shortLeverage.setter
    def shortLeverage(self, value: float) -> None:
        self._set_short_leverage(value)

    def _leverage_allowed(self, value: float) -> float:
        """The floor always applies; in Spot the only leverage is 1×."""
        if self._market == MarketType.SPOT.value:
            return SPOT_LEVERAGE
        return max(MIN_LEVERAGE, value)

    # ------------------------------------------------------------------ #
    # Market (EPIC-027D)
    # ------------------------------------------------------------------ #

    def _set_market(self, value: str) -> None:
        """Switching to Spot pins both leverages to 1× here, on the single
        writer, so no restored state or Presenter write can pair Spot with
        leverage — `BrokerSimulationConfig` would refuse that run."""
        if value == self._market:
            return
        self._market = value
        if value == MarketType.SPOT.value:
            self._set_long_leverage(SPOT_LEVERAGE)
            self._set_short_leverage(SPOT_LEVERAGE)
        self.marketChanged.emit()

    @property
    def market(self) -> str:
        return self._market

    @market.setter
    def market(self, value: str) -> None:
        self._set_market(value)

    def _set_take_profit_pct_enabled(self, value: bool) -> None:
        if value != self._take_profit_pct_enabled:
            self._take_profit_pct_enabled = bool(value)
            self.takeProfitPctEnabledChanged.emit()

    @property
    def takeProfitPctEnabled(self) -> bool:
        return self._take_profit_pct_enabled

    @takeProfitPctEnabled.setter
    def takeProfitPctEnabled(self, value: bool) -> None:
        self._set_take_profit_pct_enabled(value)

    def _set_take_profit_pct_text(self, value: str) -> None:
        if value != self._take_profit_pct_text:
            self._take_profit_pct_text = value
            self.takeProfitPctTextChanged.emit()

    @property
    def takeProfitPctText(self) -> str:
        return self._take_profit_pct_text

    @takeProfitPctText.setter
    def takeProfitPctText(self, value: str) -> None:
        self._set_take_profit_pct_text(value)

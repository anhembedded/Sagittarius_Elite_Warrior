"""`EPIC-028I` — the order panel's options beside the two sides: time in
force, reduce-only, TP/SL with each side's levels, and the Futures margin
mode and leverage.

@details Kept apart from `OrderEntryViewModel` because each changes for its
own reason: the sides change as the user types an order, these change as
the user configures how orders are sent. `apply_to` folds them into a side's
`SideInput`, which is the only way the figures see them: reduce-only on
both sides at once (one box, as on Binance), the TP/SL levels only while
the TP/SL box is on, so a level typed and then switched off never protects
anything.

The margin mode and leverage are the exchange's: the chips show the last
read (`show_setting`) and ask for a change (`marginTypeRequested`,
`leverageRequested`); the presenter sends it and reads the answer back.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.protective_levels import (
    ProtectiveLevels,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.amount_text import (
    parse_amount,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    SideInput,
)

_NO_LEVELS: tuple[Decimal | None, Decimal | None] = (None, None)


class OrderOptionsViewModel(QObject):
    """@brief How the panel's orders are sent, one instance per panel."""

    changed = Signal()
    #: Carries the `MarginType` asked for.
    marginTypeRequested = Signal(object)
    #: Carries the leverage asked for.
    leverageRequested = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._time_in_force = TimeInForce.GTC
        self._reduce_only = False
        self._tp_sl_enabled = False
        self._levels = {side: _NO_LEVELS for side in EntrySide}
        self._setting: FuturesSymbolSetting | None = None

    @property
    def time_in_force(self) -> TimeInForce:
        return self._time_in_force

    @property
    def reduce_only(self) -> bool:
        return self._reduce_only

    @property
    def tp_sl_enabled(self) -> bool:
        return self._tp_sl_enabled

    @property
    def setting(self) -> FuturesSymbolSetting | None:
        """The symbol's leverage and margin mode as last read."""
        return self._setting

    def protection(self, side: EntrySide) -> ProtectiveLevels | None:
        """`side`'s TP/SL, or `None` when TP/SL is off or nothing is typed."""
        take_profit, stop_loss = self._levels[side]
        if not self._tp_sl_enabled or (take_profit is None and stop_loss is None):
            return None
        return ProtectiveLevels(take_profit, stop_loss)

    def apply_to(self, side: EntrySide, entry: SideInput) -> SideInput:
        """`entry` with the options that change its figures."""
        levels = self.protection(side)
        return replace(
            entry,
            reduce_only=self._reduce_only,
            take_profit=levels.take_profit if levels else None,
            stop_loss=levels.stop_loss if levels else None,
        )

    def set_time_in_force(self, time_in_force: TimeInForce) -> None:
        if time_in_force is not self._time_in_force:
            self._time_in_force = time_in_force
            self.changed.emit()

    def set_reduce_only(self, reduce_only: bool) -> None:
        if reduce_only != self._reduce_only:
            self._reduce_only = reduce_only
            self.changed.emit()

    def set_tp_sl_enabled(self, enabled: bool) -> None:
        if enabled != self._tp_sl_enabled:
            self._tp_sl_enabled = enabled
            self.changed.emit()

    def set_take_profit(self, side: EntrySide, text: str) -> None:
        self._store(side, (_positive(text), self._levels[side][1]))

    def set_stop_loss(self, side: EntrySide, text: str) -> None:
        self._store(side, (self._levels[side][0], _positive(text)))

    def request_margin_type(self, margin_type: MarginType) -> None:
        self.marginTypeRequested.emit(margin_type)

    def request_leverage(self, leverage: int) -> None:
        self.leverageRequested.emit(leverage)

    def show_setting(self, setting: FuturesSymbolSetting | None) -> None:
        if setting != self._setting:
            self._setting = setting
            self.changed.emit()

    def clear_levels(self) -> None:
        """A new symbol: levels typed for the last one no longer apply."""
        self._levels = {side: _NO_LEVELS for side in EntrySide}
        self.changed.emit()

    def _store(
        self, side: EntrySide, levels: tuple[Decimal | None, Decimal | None]
    ) -> None:
        if levels != self._levels[side]:
            self._levels[side] = levels
            self.changed.emit()


def _positive(text: str) -> Decimal | None:
    value = parse_amount(text)
    return value if value is not None and value > 0 else None

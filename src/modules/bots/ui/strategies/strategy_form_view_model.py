"""What the Arm strategy dialog shows and what the person chose in it
(`EPIC-033K` stage 3; `EPIC-025` PR 2.1e made it one shared owner).

@details One per venue, owned by `VenueStrategies`: the strategy, the symbol,
the timeframe, the sizing, the leverage and the parameters the person is
editing, before arming. `StrategyArmingCoordinator` (this directory) is the
behaviour; this is only what it reads and writes, and its `StrategyFormState`
Protocol is the shape this class satisfies. The parameters are a
`ParamsSink`, the shape `StrategyParamsDialog` reads.

@par Why the symbol is a field now
The desks' strategy card armed the symbol its desk's chart showed. The Bots
mode has no such chart, so the person picks the symbol in the dialog, from
the app's symbol list, the saved arming's symbol first.

@par Picking is not arming
Every `request_*` method only records a choice. Arming is the dialog's own
button, through `VenueStrategies`; a pick that armed would be `BUG-101`
again (work run by a setter the person did not mean as a command).

@par Plain attributes, not Qt properties
The desks' card was bound to QML-era `@Property`s; the dialog reads plain
values, so `mypy` checks this class and its readers.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form import ParamsSink


class StrategyFormViewModel(QObject):
    """@brief What the arming form shows, and what the person asked it for."""

    #: The strategy picked changed: its parameter form is rebuilt. Not
    #: emitted for the timeframe, the symbol, the sizing or the leverage,
    #: whose edits must not discard parameters being typed.
    strategy_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.params = ParamsSink(self)
        self.strategy_options: tuple[tuple[str, str], ...] = ()
        self.interval_options: tuple[str, ...] = ()
        self.symbol_options: tuple[str, ...] = ()
        self.selected_strategy_key = ""
        self.live_interval = ""
        self.selected_symbol = ""
        self.sizing_percent = 0.0
        self.leverage = 1.0

    # -- filled by the coordinator ------------------------------------- #

    def set_strategy_options(
        self,
        strategy_options: Sequence[tuple[str, str]],
        interval_options: Sequence[str],
    ) -> None:
        """`(key, label)` per strategy, and the timeframes offered."""
        self.strategy_options = tuple(strategy_options)
        self.interval_options = tuple(interval_options)

    def set_strategy_selection(
        self, strategy_key: str, interval: str, sizing_percent: float, leverage: float
    ) -> None:
        self.selected_strategy_key = strategy_key
        self.live_interval = interval
        self.sizing_percent = sizing_percent
        self.leverage = leverage
        self.strategy_changed.emit()

    def set_symbol(self, symbol: str, options: Sequence[str]) -> None:
        """The symbols offered, and the one shown chosen; a chosen symbol
        missing from `options` is offered first, so a saved arming's symbol
        is never silently replaced."""
        listed = (symbol, *options) if symbol and symbol not in options else options
        self.symbol_options = tuple(listed)
        self.selected_symbol = symbol or (self.symbol_options[:1] or ("",))[0]

    def set_bot_params(self, groups: tuple[ParamGroup, ...]) -> None:
        self.params.set_groups(groups)

    def set_bot_params_error(self, message: str) -> None:
        self.params.set_error(message)

    # -- what the person chose ------------------------------------------ #

    def request_strategy(self, strategy_key: str) -> None:
        """Records the pick. Arming is a separate, explicit action."""
        if strategy_key and strategy_key != self.selected_strategy_key:
            self.selected_strategy_key = strategy_key
            self.strategy_changed.emit()

    def request_interval(self, interval: str) -> None:
        if interval:
            self.live_interval = interval

    def request_symbol(self, symbol: str) -> None:
        symbol = symbol.strip().upper()
        if symbol:
            self.selected_symbol = symbol

    def request_sizing_percent(self, percent: float) -> None:
        self.sizing_percent = percent

    def request_leverage(self, leverage: float) -> None:
        self.leverage = leverage

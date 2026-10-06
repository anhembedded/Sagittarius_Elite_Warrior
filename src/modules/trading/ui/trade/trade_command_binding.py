"""The Trade mode's commands, bound to the desk of the venue chosen
(`EPIC-033I`).

Enable live trading and New order… act on the venue the mode trades: their
enabled and checked states follow that venue's desk, and follow the next one
when the person chooses another venue. Emergency stop acts on every enabled
venue (`trade_commands.py`), and is off only while no venue is enabled. The
chart's commands (View → Chart) drive the chosen venue's chart.

Presenter-owned (`async-ui-action-rule.md` §2), never registered; the desks'
own presenters keep every action's ownership and fencing
(`DeskSessionControls`).
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_presenter import (
    DeskPresenter,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_command_mirror import (
    ChartCommandMirror,
    chart_command_actions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)

from .trade_commands import CHART_PREFIX, EMERGENCY_STOP, ENABLE_TRADING, NEW_ORDER
from .venue_choice import VenueChoice


class TradeCommandBinding(QObject):
    """@brief Routes the Trade menu's commands to the chosen venue's desk."""

    enableEnabled = Signal(bool)
    enableChecked = Signal(bool)
    newOrderEnabled = Signal(bool)

    def __init__(
        self,
        desks: Mapping[TradingVenue, DeskPresenter],
        choice: VenueChoice,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._desks = dict(desks)
        self._choice = choice
        self._chart = ChartCommandMirror(CHART_PREFIX, self)
        for desk in self._desks.values():
            desk.commandStateChanged.connect(self._announce)
        choice.changed.connect(lambda _venue: self._follow_choice())

    def bind_commands(self, binder: ICommandBinder) -> None:
        desk = self._chosen()
        binder.bind(
            ENABLE_TRADING,
            lambda _checked: self._on_toggle(),
            enabled=self.enableEnabled,
            checked=self.enableChecked,
            initially_enabled=desk is not None and not desk.toggle_busy,
        )
        binder.bind(
            NEW_ORDER,
            lambda _checked: self._on_new_order(),
            enabled=self.newOrderEnabled,
            initially_enabled=desk is not None and desk.can_take_order,
        )
        binder.bind(
            EMERGENCY_STOP,
            lambda _checked: self._on_emergency_stop(),
            initially_enabled=bool(self._desks),
        )
        self._chart.bind_commands(binder)
        # A desk built while its venue's trading is on must show Enable
        # checked; its state was set before this binding existed.
        self._follow_choice()

    def _chosen(self) -> DeskPresenter | None:
        venue = self._choice.current
        return self._desks.get(venue) if venue is not None else None

    def _follow_choice(self) -> None:
        desk = self._chosen()
        self._chart.follow_chart(
            chart_command_actions(desk.view.chart) if desk is not None else None
        )
        self._announce()

    def _announce(self) -> None:
        desk = self._chosen()
        self.enableEnabled.emit(desk is not None and not desk.toggle_busy)
        self.enableChecked.emit(desk is not None and desk.trading_enabled)
        self.newOrderEnabled.emit(desk is not None and desk.can_take_order)

    def _on_toggle(self) -> None:
        desk = self._chosen()
        if desk is not None:
            desk.request_toggle()
        # The action checked itself on the click; it shows the session's
        # state, which changes only when the toggle's answer arrives.
        self._announce()

    def _on_new_order(self) -> None:
        desk = self._chosen()
        if desk is not None:
            desk.request_new_order()

    def _on_emergency_stop(self) -> None:
        for desk in self._desks.values():
            desk.request_emergency_stop()

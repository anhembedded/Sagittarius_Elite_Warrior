"""The Trade mode's commands, bound to the desk of the venue chosen
(`EPIC-033I`).

New order…, Cancel order, Cancel all orders, Close position and View → Hide other pairs
act on the venue the mode trades: their enabled and checked states follow that venue's
desk, and follow the next one when the person chooses another venue. Emergency stop acts on every enabled
venue (`trade_commands.py`), and is off only while no venue is enabled. The
chart's commands (View → Chart) drive the chosen venue's chart.

Presenter-owned (`async-ui-action-rule.md` §2), never registered; the desks'
own presenters keep every action's ownership and fencing
(`DeskSessionControls`).
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_panel import (
    CANCEL_ALL_ACTION,
    CANCEL_ORDER_ACTION,
    CLOSE_POSITION_ACTION,
)
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
from Sagittarius_Elite_Warrior.src.support.charting.live_stream_mirror import (
    LiveStreamMirror,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_mirror import ActionMirror
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)

from .trade_commands import (
    CANCEL_ALL,
    CANCEL_ORDER,
    CHART_PREFIX,
    CLOSE_POSITION,
    EMERGENCY_STOP,
    HIDE_OTHER_PAIRS,
    NEW_ORDER,
)
from .venue_choice import VenueChoice


class TradeCommandBinding(QObject):
    """@brief Routes the Trade menu's commands to the chosen venue's desk."""

    newOrderEnabled = Signal(bool)
    venueChosen = Signal(bool)
    hideOtherPairsChecked = Signal(bool)

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
        self._live_stream = LiveStreamMirror(CHART_PREFIX, self)
        self._tables = ActionMirror(
            {
                CANCEL_ORDER_ACTION: CANCEL_ORDER,
                CANCEL_ALL_ACTION: CANCEL_ALL,
                CLOSE_POSITION_ACTION: CLOSE_POSITION,
            },
            self,
        )
        for desk in self._desks.values():
            desk.commandStateChanged.connect(self._announce)
        choice.changed.connect(lambda _venue: self._follow_choice())

    def bind_commands(self, binder: ICommandBinder) -> None:
        desk = self._chosen()
        binder.bind(
            NEW_ORDER,
            lambda _checked: self._on_new_order(),
            enabled=self.newOrderEnabled,
            initially_enabled=desk is not None and desk.can_take_order,
        )
        binder.bind(
            HIDE_OTHER_PAIRS,
            self._on_hide_other_pairs,
            enabled=self.venueChosen,
            checked=self.hideOtherPairsChecked,
            initially_enabled=desk is not None,
        )
        binder.bind(
            EMERGENCY_STOP,
            lambda _checked: self._on_emergency_stop(),
            initially_enabled=bool(self._desks),
        )
        self._chart.bind_commands(binder)
        self._live_stream.bind_commands(binder)
        self._tables.bind_commands(binder)
        self._follow_choice()

    def _chosen(self) -> DeskPresenter | None:
        venue = self._choice.current
        return self._desks.get(venue) if venue is not None else None

    def _follow_choice(self) -> None:
        desk = self._chosen()
        self._chart.follow_chart(
            chart_command_actions(desk.view.chart) if desk is not None else None
        )
        self._live_stream.follow_chart(desk.chart if desk is not None else None)
        self._tables.follow(desk.table_actions() if desk is not None else None)
        self._announce()

    def _announce(self) -> None:
        desk = self._chosen()
        self.newOrderEnabled.emit(desk is not None and desk.can_take_order)
        self.venueChosen.emit(desk is not None)
        self.hideOtherPairsChecked.emit(desk is not None and desk.hides_other_pairs)

    def _on_new_order(self) -> None:
        desk = self._chosen()
        if desk is not None:
            desk.request_new_order()

    def _on_hide_other_pairs(self, checked: bool) -> None:
        desk = self._chosen()
        if desk is not None:
            desk.set_hide_other_pairs(checked)

    def _on_emergency_stop(self) -> None:
        for desk in self._desks.values():
            desk.request_emergency_stop()

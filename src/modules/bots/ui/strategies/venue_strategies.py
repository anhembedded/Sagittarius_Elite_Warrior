"""The Bots mode's strategy rows, end to end (`EPIC-033K` stage 3).

@details One row per venue this run serves (`StrategiesPanel`). For each,
the venue's own ports (`VenueStrategyControls`: the Spot row arms Spot, never
the primary venue), its own form (`StrategyFormViewModel`) and its own
`StrategyArmingCoordinator`; nothing passes between the venues
(`EPIC-028L`).

- **Bots → Arm strategy…** fills the selected venue's form from its saved
  arming, asks through `ArmStrategyDialog`, and arms on Arm strategy. It is
  enabled while a row is selected, nothing is armed there, that venue's
  trading is off and no arm or disarm is in flight.
- **Bots → Disarm strategy** disarms the selected venue; enabled while a
  strategy is armed there, that venue's trading is off and nothing is in
  flight. It takes no confirmation: nothing is sold or cancelled.

Both are off while the venue trades: the visible half of `EPIC-022` §4.1's
rule, which the desks' card kept (`EPIC-023D`) and the session enforces
regardless (PR #376 review). They follow `TradingSwitchChangedEvent`.

The rows show what the session has armed, never what a form shows: they are
re-read from `IArmedStrategyReader` after each arm or disarm and whenever an
`ArmedStrategyChangedEvent` arrives (`on_changed`), so an arm from elsewhere
(the strategy module's boot restore) is shown too.

Presenter-owned (`async-ui-action-rule.md` §2): `BotsPresenter` builds it,
subscribes it to the event and binds its commands. Arming is a synchronous
dispatch on the UI thread, as the desks' card did; the tracker records each
action so a second command waits for it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    SUPPORTED_LIVE_INTERVALS,
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.armed_strategy_changed_event import (
    ArmedStrategyChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_catalog_reader import (
    IStrategyCatalogReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_strategy_controls import (
    VenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.derived_state import DerivedState

from .arm_strategy_dialog import AskArmStrategy
from .strategy_arming_coordinator import StrategyArmingCoordinator
from .strategy_form_view_model import StrategyFormViewModel
from .strategy_rows import StrategiesPanel, StrategyRow

logger = logging.getLogger("App.Bots.Strategies")

_ARM = "arm_strategy"


@dataclass(frozen=True)
class StrategyPorts:
    """What the strategy rows need, resolved once by the presenter."""

    #: Each served venue's live strategy ports, in the order the rows list
    #: them.
    venues: Sequence[VenueStrategyControls]
    catalog: IStrategyCatalogReader
    #: The symbols the arming form offers, the app's list.
    symbol_options: Sequence[str]
    #: Asks what a venue arms; `True` arms.
    ask: AskArmStrategy
    #: The Bots panel's status line: `(text, is_error)`.
    set_status: Callable[[str, bool], None]
    #: How a refused or failed arm or disarm reaches the user (`BOT-169`).
    notifier: INotifier
    #: Whether a venue's live trading is on now.
    trading_on: Callable[[TradingVenue], bool]


class _Venue:
    """One venue's form, coordinator and armed state."""

    def __init__(
        self, controls: VenueStrategyControls, ports: StrategyPorts, owner: QObject
    ) -> None:
        self.controls = controls
        self.form = StrategyFormViewModel(owner)
        self.busy = False
        self.coordinator = StrategyArmingCoordinator(
            view_model=self.form,
            catalog=ports.catalog,
            arming=controls.arming,
            get_active_symbol=lambda: self.form.selected_symbol,
            get_armed_config=self.armed,
            tracker=ActionOwnershipTracker(),
            arm_action_kind=_ARM,
            set_status=ports.set_status,
            notifier=ports.notifier,
            append_log=lambda line: logger.info(
                "[strategies] %s: %s", controls.venue.value, line
            ),
            on_armed_changed=self._on_busy,
        )
        self.form.strategy_changed.connect(
            self.coordinator.on_strategy_selection_changed
        )
        self.form.params.botParamsSaveRequested.connect(self.coordinator.apply_params)
        self._on_change: Callable[[], None] = lambda: None

    def armed(self) -> ArmedStrategyConfig | None:
        return self.controls.armed.armed().config

    def row(self) -> StrategyRow:
        armed = self.armed()
        summary = self.coordinator.armed_summary(armed)
        return StrategyRow(
            self.controls.venue, summary, self.busy, self._saved_summary(armed)
        )

    def _saved_summary(self, armed: ArmedStrategyConfig | None) -> str:
        """`BOT-166`: what the last session armed, shown while nothing is."""
        if armed is not None:
            return ""
        saved = self.controls.arming.saved_selection()
        if not (saved.strategy_key and saved.symbol and saved.interval):
            return ""
        return self.coordinator.armed_summary(saved)

    def fill_form(self, symbol_options: Sequence[str]) -> None:
        """The saved arming's choices, freshly, and nothing armed by it."""
        self.coordinator.restore_into_view_model(list(SUPPORTED_LIVE_INTERVALS))
        saved = self.controls.arming.saved_selection()
        self.form.set_symbol(saved.symbol, list(symbol_options))

    def follow(self, on_change: Callable[[], None]) -> None:
        self._on_change = on_change

    def _on_busy(self, _config: ArmedStrategyConfig | None, busy: bool) -> None:
        self.busy = busy
        self._on_change()


class VenueStrategies(QObject):
    """@brief The strategy rows and their two commands."""

    #: What the two commands show changed: a selection, an arm or disarm in
    #: flight or finished, or what a venue has armed.
    commands_changed = Signal()

    def __init__(
        self,
        panel: StrategiesPanel,
        ports: StrategyPorts,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._panel = panel
        self._ports = ports
        self._venues: Mapping[TradingVenue, _Venue] = {
            controls.venue: _Venue(controls, ports, self) for controls in ports.venues
        }
        for venue in self._venues.values():
            venue.follow(self.refresh)
        panel.venue_selected.connect(lambda _venue: self.commands_changed.emit())
        self.refresh()

    # -- what the commands act on --------------------------------------- #

    def _selected(self) -> _Venue | None:
        venue = self._panel.selected_venue
        return self._venues.get(venue) if venue is not None else None

    def _in_flight(self) -> bool:
        return any(venue.busy for venue in self._venues.values())

    def _changeable(self) -> _Venue | None:
        """The selected venue, while its strategy may change: its trading
        off and no arm or disarm in flight."""
        selected = self._selected()
        if selected is None or self._in_flight():
            return None
        if self._ports.trading_on(selected.controls.venue):
            return None
        return selected

    def can_arm(self) -> bool:
        selected = self._changeable()
        return selected is not None and selected.armed() is None

    def can_disarm(self) -> bool:
        selected = self._changeable()
        return selected is not None and selected.armed() is not None

    # -- the commands -------------------------------------------------- #

    def bind_commands(
        self, binder: ICommandBinder, arm_id: str, disarm_id: str
    ) -> None:
        arm = DerivedState(self.commands_changed, self.can_arm, self)
        binder.bind(
            arm_id,
            lambda _checked: self.arm_selected(),
            enabled=arm.changed,
            initially_enabled=arm.value,
        )
        disarm = DerivedState(self.commands_changed, self.can_disarm, self)
        binder.bind(
            disarm_id,
            lambda _checked: self.disarm_selected(),
            enabled=disarm.changed,
            initially_enabled=disarm.value,
        )

    def arm_selected(self) -> None:
        """Bots → Arm strategy…: asks, then arms what the form holds."""
        selected = self._selected()
        if selected is None or not self.can_arm():
            return
        selected.fill_form(self._ports.symbol_options)
        if not self._ports.ask(selected.controls.venue, selected.form):
            logger.info(
                "[strategies] arming %s: cancelled", selected.controls.venue.value
            )
            return
        selected.coordinator.on_arm_clicked()
        self.refresh()

    def disarm_selected(self) -> None:
        """Bots → Disarm strategy."""
        selected = self._selected()
        if selected is None or not self.can_disarm():
            return
        selected.coordinator.on_disarm_clicked()
        self.refresh()

    # -- what the rows show --------------------------------------------- #

    def rows(self) -> tuple[StrategyRow, ...]:
        """One row per venue, as the panel shows them."""
        return tuple(venue.row() for venue in self._venues.values())

    @property
    def subscriptions(self) -> tuple[tuple[type, Callable[..., None]], ...]:
        """What the presenter subscribes, for its lifetime (`self.subscribe`)."""
        return (
            (ArmedStrategyChangedEvent, self.on_changed),
            (TradingSwitchChangedEvent, self.on_trading_switched),
        )

    def on_trading_switched(self, event: TradingSwitchChangedEvent) -> None:
        """A venue's trading turned on or off: the commands follow."""
        if event.venue in self._venues:
            self.commands_changed.emit()

    def on_changed(self, event: ArmedStrategyChangedEvent) -> None:
        """A venue's armed strategy changed, from here or elsewhere."""
        if event.venue in self._venues:
            self.refresh()

    def refresh(self) -> None:
        self._panel.show_rows(self.rows())
        self.commands_changed.emit()

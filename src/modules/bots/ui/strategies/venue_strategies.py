"""The Bots mode's strategies, end to end (`EPIC-033K` stage 3, `BOT-219`).

@details Each venue this run serves has its own ports (`VenueStrategyControls`: the Spot venue
arms Spot, never the primary venue), its own form (`StrategyFormViewModel`) and its own
`StrategyArmingCoordinator`; nothing passes between the venues (`EPIC-028L`). There is no panel:
the owner chose, 2026-10-21, two commands and what they ask.

- **Bots → Arm strategy…** fills the form of every venue with nothing armed from its saved arming,
  asks through `ArmStrategyDialog` what to arm and on which venue, and arms on Arm strategy. It is
  enabled while a venue has nothing armed and no arm or disarm is in flight. Arming opens the
  venue's order session itself after reconciling the account (`EPIC-034C`).
- **Bots → Disarm strategy…** asks which venue's strategy to disarm, unless one is armed; enabled
  while a strategy is armed and nothing is in flight. It takes no confirmation: nothing is sold or
  cancelled. A position open on the strategy's symbol refuses it, in words
  (`DISARM_BLOCKED_MESSAGE`).

What is armed is told in the Output pane whenever an `ArmedStrategyChangedEvent` arrives
(`on_changed`), so an arm from elsewhere (the strategy module's boot restore) is told too, and in
the Arm dialog, which lists what is armed already.

Presenter-owned (`async-ui-action-rule.md` §2): `BotsPresenter` builds it, subscribes it to the
event and binds its commands. Arming is a synchronous dispatch on the UI thread; the tracker
records each action so a second command waits for it.
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

from .arm_strategy_dialog import ArmQuestion, AskArmStrategy
from .disarm_choice import ChooseVenue, VenueQuestion
from .strategy_arming_coordinator import StrategyArmingCoordinator
from .strategy_form_view_model import StrategyFormViewModel

logger = logging.getLogger("App.Bots.Strategies")

_ARM = "arm_strategy"
DISARM_TITLE = "Disarm Strategy"
DISARM_PROMPT = "Which strategy do you want to disarm?"
DISARM_TEXT = "Disarm strategy"


@dataclass(frozen=True)
class StrategyPorts:
    """What the strategy commands need, resolved once by the presenter."""

    #: Each served venue's live strategy ports.
    venues: Sequence[VenueStrategyControls]
    catalog: IStrategyCatalogReader
    #: The symbols the arming form offers, the app's list.
    symbol_options: Sequence[str]
    #: Asks what to arm and on which venue; the venue, or `None` when cancelled.
    ask: AskArmStrategy
    #: Asks which armed venue to disarm; the venue, or `None` when cancelled.
    choose: ChooseVenue
    #: The Bots panel's status line: `(text, is_error)`.
    set_status: Callable[[str, bool], None]
    #: One line in the Output pane.
    tell: Callable[[str], None]
    #: How a refused or failed arm or disarm reaches the user (`BOT-169`).
    notifier: INotifier


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

    def armed_words(self) -> str:
        """What is armed here, in words; `""` while nothing is."""
        return self.coordinator.armed_summary(self.armed())

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
    """@brief The two strategy commands and what they ask."""

    #: What the two commands show changed: an arm or disarm in flight or
    #: finished, or what a venue has armed.
    commands_changed = Signal()

    def __init__(
        self,
        ports: StrategyPorts,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._ports = ports
        self._venues: Mapping[TradingVenue, _Venue] = {
            controls.venue: _Venue(controls, ports, self) for controls in ports.venues
        }
        for venue in self._venues.values():
            venue.follow(self.commands_changed.emit)

    # -- what the commands act on --------------------------------------- #

    def _in_flight(self) -> bool:
        return any(venue.busy for venue in self._venues.values())

    def _armed(self) -> tuple[_Venue, ...]:
        return tuple(v for v in self._venues.values() if v.armed() is not None)

    def _armable(self) -> tuple[_Venue, ...]:
        return tuple(v for v in self._venues.values() if v.armed() is None)

    def can_arm(self) -> bool:
        return bool(self._armable()) and not self._in_flight()

    def can_disarm(self) -> bool:
        return bool(self._armed()) and not self._in_flight()

    def armed_lines(self) -> tuple[str, ...]:
        """What is armed now, a line a venue, for the Arm dialog."""
        return tuple(
            f"{venue.controls.venue.display_name}: {venue.armed_words()}"
            for venue in self._armed()
        )

    # -- the commands -------------------------------------------------- #

    def bind_commands(
        self, binder: ICommandBinder, arm_id: str, disarm_id: str
    ) -> None:
        arm = DerivedState(self.commands_changed, self.can_arm, self)
        binder.bind(
            arm_id,
            lambda _checked: self.arm(),
            enabled=arm.changed,
            initially_enabled=arm.value,
        )
        disarm = DerivedState(self.commands_changed, self.can_disarm, self)
        binder.bind(
            disarm_id,
            lambda _checked: self.disarm(),
            enabled=disarm.changed,
            initially_enabled=disarm.value,
        )

    def arm(self) -> None:
        """Bots → Arm strategy…: asks what to arm and where, then arms what the form holds."""
        if not self.can_arm():
            return
        candidates = self._armable()
        for venue in candidates:
            venue.fill_form(self._ports.symbol_options)
        chosen = self._ports.ask(
            ArmQuestion(
                {venue.controls.venue: venue.form for venue in candidates},
                self.armed_lines(),
            )
        )
        if chosen is None or chosen not in (v.controls.venue for v in candidates):
            logger.info("[strategies] arming: cancelled")
            return
        if not self.can_arm() or self._venues[chosen].armed() is not None:
            # The questions ran nested event loops: that venue was armed, or an action went in
            # flight, while they were open.
            logger.info("[strategies] arming: %s changed while asking", chosen.value)
            return
        self._venues[chosen].coordinator.on_arm_clicked()
        self.commands_changed.emit()

    def disarm(self) -> None:
        """Bots → Disarm strategy…: asks which venue's strategy, unless only one is armed."""
        if not self.can_disarm():
            return
        armed = self._armed()
        venue = armed[0].controls.venue if len(armed) == 1 else self._ask_which(armed)
        if venue is None:
            logger.info("[strategies] disarming: cancelled")
            return
        self._venues[venue].coordinator.on_disarm_clicked()
        self.commands_changed.emit()

    def _ask_which(self, armed: Sequence[_Venue]) -> TradingVenue | None:
        options = tuple(
            (v.controls.venue, f"{v.controls.venue.display_name}: {v.armed_words()}")
            for v in armed
        )
        return self._ports.choose(
            VenueQuestion(DISARM_TITLE, DISARM_PROMPT, DISARM_TEXT, options)
        )

    # -- what is told --------------------------------------------------- #

    @property
    def subscriptions(self) -> tuple[tuple[type, Callable[..., None]], ...]:
        """What the presenter subscribes, for its lifetime (`self.subscribe`)."""
        return ((ArmedStrategyChangedEvent, self.on_changed),)

    def on_changed(self, event: ArmedStrategyChangedEvent) -> None:
        """A venue's armed strategy changed, from here or elsewhere: said in the Output pane."""
        venue = self._venues.get(event.venue)
        if venue is None:
            return
        name = venue.controls.venue.display_name
        if event.armed:
            self._ports.tell(f"Strategy armed on {name}: {venue.armed_words()}")
        else:
            self._ports.tell(f"Strategy disarmed on {name}.")
        self.commands_changed.emit()

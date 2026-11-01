"""`EPIC-047E` PR 3b - Arm strategy… and Disarm strategy… in the VPS Bots tab: the host arms and disarms its own.

@details On this computer the two commands fill a form from the venue's saved arming and arm it through this computer's
ports (`VenueStrategies`). In the VPS tab there is no local venue; the strategy that is armed is the one the host's own
saved arming holds (owner decision O2 of `EPIC-045G`: never typed, its parameters are many and unbounded), so the tab asks
only which venue and carries the command to the host's own gate, as `bot arm-strategy` and `bot disarm-strategy` do:

- **Arm strategy…** asks the venue; on a mainnet venue it asks the real-money question (a strategy places orders by
  itself once armed), and the host judges the answer (`confirmed_venue`). The host says in its own words whether it
  armed, or why not (no saved arming, something armed already, a position open, the real money not confirmed).
- **Disarm strategy…** asks the venue; it sells and cancels nothing, so it asks nothing more.

Both are enabled while no earlier one waits; with the link down the dispatcher refuses in words and nothing is sent. The
command runs off the UI thread (a host answers in about a second) and its words come back to the Output pane and the
status line. What is armed is not shown here: the host publishes no armed-strategy fact yet, so the tab does not guess.

@par Extension cases
  · showing what is armed on the host - one more host fact and a line in `on_result`; the commands do not change;
  · a second host - another `HostStrategies` over its own dispatcher.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ArmStrategyForHostCommand,
    DisarmStrategyForHostCommand,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.derived_state import DerivedState
from Sagittarius_Elite_Warrior.src.support.ui_kit.ui_thread_relay import UiThreadRelay
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .disarm_choice import ChooseVenue, VenueQuestion

logger = logging.getLogger("App.Bots.Strategies")

ARM_TITLE = "Arm Strategy"
ARM_PROMPT = "On which venue should the VPS host arm its saved strategy?"
ARM_TEXT = "Arm on the VPS"
DISARM_TITLE = "Disarm Strategy"
DISARM_PROMPT = "On which venue should the VPS host disarm its strategy?"
DISARM_TEXT = "Disarm on the VPS"
#: What the real-money question says an arm does (`IRealMoneyConsent.confirmed`'s `action`).
ARM_REAL_MONEY = "arm a strategy that places orders by itself"
NOT_SENT = "The command could not be sent to the host; see the log."


@dataclass(frozen=True)
class HostStrategyPorts:
    """What the two commands need, given once by the backend."""

    commands: ICommandDispatcher
    threads: IThreadManager
    #: The venues offered; the host refuses one it does not serve, in words.
    venues: Sequence[TradingVenue]
    choose: ChooseVenue
    #: The real-money question: `True` when the person typed the venue.
    allow_real_money: Callable[[TradingVenue, str], bool]
    set_status: Callable[[str, bool], None]
    tell: Callable[[str], None]


def _ignoring_checked(act: Callable[[], None]) -> Callable[[bool], None]:
    def handler(_checked: bool) -> None:
        act()

    return handler


class _Answers(UiThreadRelay):
    """A worker's answer, delivered on the UI thread."""

    def __init__(self, deliver: Callable[[BotCommandResult | None], None]) -> None:
        super().__init__()
        self._deliver_to = deliver

    def answer(self, result: BotCommandResult | None) -> None:
        """Called on a worker thread: the result (or `None` when the dispatch failed) goes to the UI thread."""
        self._report(result)

    def _deliver(self, payload: object) -> None:
        self._deliver_to(payload if isinstance(payload, BotCommandResult) else None)


class HostStrategies(QObject):
    """@brief Arm and Disarm strategy, carried to the VPS host."""

    commands_changed = Signal()

    def __init__(self, ports: HostStrategyPorts, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ports = ports
        self._waiting = False
        self._answers = _Answers(self._on_answer)

    @property
    def subscriptions(self) -> tuple[tuple[type, Callable[..., None]], ...]:
        """Nothing: the host publishes no armed-strategy event."""
        return ()

    def can_act(self) -> bool:
        return not self._waiting

    def bind_commands(
        self, binder: ICommandBinder, arm_id: str, disarm_id: str
    ) -> None:
        free = DerivedState(self.commands_changed, self.can_act, self)
        for command_id, act in ((arm_id, self.arm), (disarm_id, self.disarm)):
            binder.bind(
                command_id,
                _ignoring_checked(act),
                enabled=free.changed,
                initially_enabled=free.value,
            )

    def arm(self) -> None:
        venue = self._asked(ARM_TITLE, ARM_PROMPT, ARM_TEXT)
        if venue is None:
            return
        confirmed = None
        if venue.is_mainnet:
            if not self._ports.allow_real_money(venue, ARM_REAL_MONEY):
                logger.info(
                    "[strategies] arming on %s: not confirmed", venue.identifier
                )
                return
            confirmed = venue.identifier
        self._send(ArmStrategyForHostCommand(venue.identifier, confirmed))

    def disarm(self) -> None:
        venue = self._asked(DISARM_TITLE, DISARM_PROMPT, DISARM_TEXT)
        if venue is not None:
            self._send(DisarmStrategyForHostCommand(venue.identifier))

    def _asked(self, title: str, prompt: str, ok_text: str) -> TradingVenue | None:
        if self._waiting:
            return None
        options = tuple((venue, venue.display_name) for venue in self._ports.venues)
        return self._ports.choose(VenueQuestion(title, prompt, ok_text, options))

    def _send(
        self, command: ArmStrategyForHostCommand | DisarmStrategyForHostCommand
    ) -> None:
        if self._waiting:  # the question ran a nested event loop: another command may have gone out meanwhile
            return
        self._waiting = True
        self.commands_changed.emit()
        logger.info("[strategies] %s sent to the host", type(command).__name__)
        try:
            self._ports.threads.submit(self._dispatch, command)
        except Exception:
            logger.exception(
                "[strategies] %s could not be queued", type(command).__name__
            )
            self._on_answer(None)

    def _dispatch(self, command: object) -> None:
        """On a pool thread: one dispatch, its words handed to the UI thread."""
        try:
            result = self._ports.commands.dispatch(type(command), command)
        except Exception:
            logger.exception("[strategies] %s failed", type(command).__name__)
            self._answers.answer(None)
            return
        self._answers.answer(result if isinstance(result, BotCommandResult) else None)

    def _on_answer(self, result: BotCommandResult | None) -> None:
        self._waiting = False
        words = NOT_SENT if result is None else result.message
        accepted = result is not None and result.accepted
        if words:
            self._ports.tell(words)
            self._ports.set_status(words, not accepted)
        self.commands_changed.emit()

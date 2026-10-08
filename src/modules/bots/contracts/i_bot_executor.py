"""`EPIC-029B` — the seam a kind's executor sits behind (ADR D2, D9).

The executor is the actor that runs one bot (`EPIC-029E`): it places and
cancels the bot's orders through trading and reports lifecycle events back.
Each method is a command: it asks the actor to begin, and the actor reports the
outcome as a lifecycle event (`ladder_ready`, `start_refused`,
`stop_confirmed`, `fault`), never as a return value, because every one of these
takes exchange round trips the caller must not wait on.

`EPIC-029E` adds the facts every kind hears — fills, ends, ticks and the
trading switch — and builds the Grid's executor (`GridExecutor`). Each fact is
copied off the caller's thread and queued (ADR D9).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderEnd,
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)


class BaseHandling(str, Enum):
    """What Stop does with the base asset the bot bought (ADR O3)."""

    KEEP = "KEEP"
    SELL_AT_MARKET = "SELL_AT_MARKET"


class IBotExecutor(ABC):
    """Runs one bot. Every method asks; the outcome arrives as a lifecycle event."""

    @abstractmethod
    def start(self) -> None:
        """Place the opening buy and the ladder (ADR §3.4, D21)."""

    @abstractmethod
    def pause(self) -> None:
        """Stop placing; keep recording fills."""

    @abstractmethod
    def resume(self) -> None:
        """Place what the pause held back, or re-plan from HALTED (ADR D13)."""

    @abstractmethod
    def stop(self, base: BaseHandling) -> None:
        """Cancel every tagged order, then keep or sell the base (ADR O3)."""

    @abstractmethod
    def confirm_resume(self) -> None:
        """Lay the ladder a resume from HALTED proposed (ADR D13, O2)."""

    @abstractmethod
    def has_resume_proposal(self) -> bool:
        """A resume from HALTED proposed a ladder that awaits confirmation."""

    @abstractmethod
    def on_fill(self, fill: BotOrderFill) -> None:
        """One of the bot's orders filled, fully or partly."""

    @abstractmethod
    def on_end(self, end: BotOrderEnd) -> None:
        """One of the bot's orders ended without filling whole."""

    @abstractmethod
    def on_tick(self, price: Decimal) -> None:
        """The bot's symbol traded at `price` (stop loss and take profit, D11)."""

    @abstractmethod
    def on_switch(self, enabled: bool, cause: TradingSwitchCause) -> None:
        """Trading on the bot's venue was enabled, disabled or Emergency-Stopped."""

    @abstractmethod
    def reconcile_after_gap(self) -> None:
        """The venue's user-data stream was down and is back, or a periodic
        check came due: bring the ladder level with the exchange (`EPIC-035B`)."""

    @abstractmethod
    def halt_user_stream_down(self, down_for: timedelta) -> None:
        """The user-data stream has been down for `down_for`: halt and park
        the ladder, because no fill can be seen (`EPIC-035B`)."""


class IBotExecutorFactory(ABC):
    """Builds the executor for one bot of one kind."""

    @abstractmethod
    def create(self, bot: Bot) -> IBotExecutor:
        """A new executor for `bot`."""

"""The facts a bot's executor hears from outside — fills, ends, ticks, the
trading switch, the user-data stream (`EPIC-029E`, `EPIC-035A`, `EPIC-035B`).

Split from `IBotExecutor` (the commands a user gives) so that each port has one
audience: the event handlers and watches that report what happened never see
Start or Stop, and the use cases never see a tick. Each method copies its
argument off the caller's thread and queues it behind the bot's other work
(ADR D9); none returns an outcome.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderEnd,
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)


class IBotFacts(ABC):
    """What happened that the bot must react to."""

    @abstractmethod
    def on_fill(self, fill: BotOrderFill) -> None:
        """One of the bot's orders filled, fully or partly."""

    @abstractmethod
    def on_end(self, end: BotOrderEnd) -> None:
        """One of the bot's orders ended without filling whole."""

    @abstractmethod
    def on_tick(self, tick: PriceTick) -> None:
        """The bot's symbol traded at `tick.last`, within `tick.low`..`tick.high`
        (stop loss and take profit, D11; the range is `BUG-191`)."""

    @abstractmethod
    def on_price_age_check(self) -> None:
        """Time passed: halt if the bot holds orders and its price feed went
        quiet (`EPIC-035A`)."""

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

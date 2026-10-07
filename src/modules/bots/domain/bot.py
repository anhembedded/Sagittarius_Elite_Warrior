"""`EPIC-029B` — the Bot aggregate (ADR D2).

A bot is what the user created: a name, a kind (Grid today), the venue and
symbol it trades, and the kind's parameters. Around that definition it carries
its lifecycle state and two timestamps. It is immutable; every change returns a
new `Bot`, and every state change goes through `bot_lifecycle_fsm_matrix.py`.

@par `run_started_at` (ADR D6, review round 2)
Stamped by `start` from DRAFT or STOPPED, and kept through STARTING, RUNNING,
PAUSED, RECOVERING, HALTED and STOPPING. Trading derives the bot's inventory per
run from the tagged executions since this instant (`EPIC-029A`), so it must not
move when the bot halts and resumes; a resume from HALTED is the same run.

@par `recovering_from`
The state `reconcile_ok` returns to. Recorded when the bot enters RECOVERING
from RUNNING or PAUSED, kept while it stays there, cleared when it leaves.

@par The venue
A bot's orders, lease and derived inventory are tied to its venue (ADR D6), so it
is fixed once the bot has run. A bot that is still a DRAFT and **never ran** has
none of those, and may move between the Spot venues (`moved_to`); every other bot,
and any Futures bot, may not (`venue_locked_reason`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RECOVERABLE_STATES,
    RUN_STARTING_STATES,
    BotLifecycleEvent,
    BotLifecycleState,
    BotLifecycleTarget,
    InvalidBotTransitionError,
    next_target,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class BotVenueFixedError(ValueError):
    """The bot's venue cannot change; the message says why, in words."""


@dataclass(frozen=True, slots=True)
class BotDefinition:
    """What the user chose. `config` is the kind's parameters, as strings.

    Strings, not numbers: the kind parses them (`Decimal` for money), so the
    definition round-trips through JSON without a float ever touching a price.
    """

    name: str
    kind: str
    venue: TradingVenue
    symbol: str
    config: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("A bot needs a name")
        if not self.symbol.strip():
            raise ValueError("A bot needs a symbol")
        object.__setattr__(self, "config", MappingProxyType(dict(self.config)))


@dataclass(frozen=True, slots=True)
class BotLifecycle:
    """Where the bot is, and the two facts the table needs beyond the state."""

    state: BotLifecycleState
    run_started_at: datetime | None = None
    recovering_from: BotLifecycleState | None = None


@dataclass(frozen=True, slots=True)
class Bot:
    """One bot: identity, definition, lifecycle and creation time."""

    bot_id: BotId
    definition: BotDefinition
    lifecycle: BotLifecycle
    created_at: datetime

    @classmethod
    def draft(cls, bot_id: BotId, definition: BotDefinition, at: datetime) -> Bot:
        """A new bot, never started."""
        return cls(bot_id, definition, BotLifecycle(BotLifecycleState.DRAFT), at)

    @property
    def state(self) -> BotLifecycleState:
        return self.lifecycle.state

    def apply(self, event: BotLifecycleEvent, at: datetime) -> Bot:
        """The bot after `event`, which happened at `at`.

        @raise InvalidBotTransitionError The table does not declare it, or it is
            `delete` (use `require_deletable`: a removed bot has no next value).
        """
        target = next_target(self.state, event)
        if target is BotLifecycleTarget.REMOVED:
            raise InvalidBotTransitionError(self.state, event)
        next_state = self._resolve(target)
        return replace(self, lifecycle=self._next_lifecycle(event, next_state, at))

    def edited(self, definition: BotDefinition, at: datetime) -> Bot:
        """The bot with new parameters; only DRAFT and STOPPED accept an edit."""
        return replace(self.apply(BotLifecycleEvent.EDIT, at), definition=definition)

    @property
    def venue_locked_reason(self) -> str:
        """Why the venue cannot change now, or `""` when it can."""
        if self.definition.venue.market_type is not MarketType.SPOT:
            return "Only a Spot bot can change its venue."
        if self.state is not BotLifecycleState.DRAFT:
            return f"A bot's venue is fixed once it has run; this one is {self.state.value.lower()}."
        if self.lifecycle.run_started_at is not None:
            return "A bot's venue is fixed once it has run."
        return ""

    def moved_to(self, venue: TradingVenue) -> Bot:
        """The bot on another Spot venue.

        @raise BotVenueFixedError The bot may not change its venue, or `venue`
            is not a Spot venue.
        """
        if reason := self.venue_locked_reason:
            raise BotVenueFixedError(reason)
        if venue.market_type is not MarketType.SPOT:
            raise BotVenueFixedError(f"{venue.display_name} is not a Spot venue.")
        return replace(self, definition=replace(self.definition, venue=venue))

    def restored(self, at: datetime) -> Bot:
        """The bot as it is after an app restart (ADR D12)."""
        return self.apply(BotLifecycleEvent.APP_RESTART, at)

    def require_deletable(self) -> None:
        """@raise InvalidBotTransitionError The bot is not DRAFT or STOPPED."""
        if next_target(self.state, BotLifecycleEvent.DELETE) is not (
            BotLifecycleTarget.REMOVED
        ):
            raise InvalidBotTransitionError(self.state, BotLifecycleEvent.DELETE)

    def _resolve(
        self, target: BotLifecycleState | BotLifecycleTarget
    ) -> BotLifecycleState:
        if isinstance(target, BotLifecycleState):
            return target
        recovering_from = self.lifecycle.recovering_from
        if recovering_from is None:
            raise InvalidBotTransitionError(self.state, BotLifecycleEvent.RECONCILE_OK)
        return recovering_from

    def _next_lifecycle(
        self, event: BotLifecycleEvent, next_state: BotLifecycleState, at: datetime
    ) -> BotLifecycle:
        run_started_at = self.lifecycle.run_started_at
        if event is BotLifecycleEvent.START and self.state in RUN_STARTING_STATES:
            run_started_at = at
        recovering_from: BotLifecycleState | None = None
        if next_state is BotLifecycleState.RECOVERING:
            recovering_from = (
                self.state
                if self.state in RECOVERABLE_STATES
                else self.lifecycle.recovering_from
            )
        return BotLifecycle(next_state, run_started_at, recovering_from)

"""`EPIC-040C` — a backtest's parameters: a copy of a bot's saved plan, never the bot's own.

A person tries a "what if" by editing a copy. The copy starts from the bot's **saved** plan (not the
Plan panel's unsaved edits), remembers what it was copied from so it can say what differs and be
reset to it, and belongs to no bot: nothing here writes a bot, sends an order or reads the account.
Judging it is the kind's own `IBotKind.validate` with no account (`ui/backtest/sandbox_judge.py`),
and running it is the kind's `IKindBacktester` (`EPIC-040B`).

The value is frozen: an edit and a reset return a new plan, so a presenter can hold the last one and
a test can compare two.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class SandboxPlan:
    """One simulation's parameters, and the saved plan they were copied from."""

    kind_id: str
    venue: TradingVenue
    symbol: str
    #: The parameters being tried: what the sandbox runs.
    config: Mapping[str, str]
    #: The bot's saved plan at the time of the copy: what Reset restores and what is compared.
    source_config: Mapping[str, str]
    source_bot_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "config", MappingProxyType(dict(self.config)))
        object.__setattr__(
            self, "source_config", MappingProxyType(dict(self.source_config))
        )

    @classmethod
    def from_bot(cls, bot: BotSnapshot) -> SandboxPlan:
        """A sandbox starting from `bot`'s saved plan."""
        return cls(bot.kind, bot.venue, bot.symbol, bot.config, bot.config, bot.bot_id)

    def changed_fields(self) -> tuple[str, ...]:
        """The parameters whose value differs from the source, or that only one side has, sorted."""
        keys = self.config.keys() | self.source_config.keys()
        return tuple(
            sorted(
                key
                for key in keys
                if self.config.get(key) != self.source_config.get(key)
            )
        )

    @property
    def edited(self) -> bool:
        return bool(self.changed_fields())

    def with_config(self, config: Mapping[str, str]) -> SandboxPlan:
        """The same sandbox with `config` as the parameters being tried."""
        return replace(self, config=config)

    def reset(self) -> SandboxPlan:
        """The same sandbox with the source's parameters again."""
        return replace(self, config=self.source_config)

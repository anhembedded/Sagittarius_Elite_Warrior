"""`EPIC-029B` — where bots are kept between runs (ADR D4).

One record per bot: the `Bot` (definition, lifecycle, timestamps) and the
kind's `runtime` — the ladder state the executor writes (`EPIC-029E`), opaque
to everything but that kind. The store is **never** an input to a safety check:
inventory comes from exchange evidence (ADR D6), so a hand-edited file can
mislead a display, never a gate.

@par A bad file is refused by name, never dropped
`load_all()` returns the bots it could read **and** the files it refused, each
with its reason. A file written by a newer version (`schema_version` it does
not know), or one that is not valid JSON, would otherwise vanish from the list
while its bot may still own orders on the exchange.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


@dataclass(frozen=True, slots=True)
class StoredBot:
    """One bot as the store holds it."""

    bot: Bot
    runtime: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime", MappingProxyType(dict(self.runtime)))


@dataclass(frozen=True, slots=True)
class RefusedBotFile:
    """A file the store found and would not load, and why."""

    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class BotStoreReading:
    """Everything one `load_all()` found."""

    bots: tuple[StoredBot, ...] = ()
    refused: tuple[RefusedBotFile, ...] = ()


class BotNotFoundError(LookupError):
    """No bot with this id is stored."""

    def __init__(self, bot_id: BotId) -> None:
        super().__init__(f"No bot {bot_id} is stored")
        self.bot_id = bot_id


class UnreadableBotError(ValueError):
    """The bot's file exists but cannot be loaded (unknown schema, bad JSON)."""

    def __init__(self, name: str, reason: str) -> None:
        super().__init__(f"Bot file {name} cannot be loaded: {reason}")
        self.name = name
        self.reason = reason


class IBotStore(ABC):
    """Saves, loads and deletes bots. Writes to one bot are serialised."""

    @abstractmethod
    def save(self, stored: StoredBot) -> None:
        """Write the bot, replacing any earlier record of it, atomically."""

    @abstractmethod
    def load(self, bot_id: BotId) -> StoredBot:
        """@raise BotNotFoundError No such bot.
        @raise UnreadableBotError Its file cannot be loaded."""

    @abstractmethod
    def load_all(self) -> BotStoreReading:
        """Every bot, plus every file refused with its reason."""

    @abstractmethod
    def delete(self, bot_id: BotId) -> None:
        """Forget the bot. @raise BotNotFoundError No such bot."""

    @abstractmethod
    def exists(self, bot_id: BotId) -> bool:
        """Whether an id is taken, including by a file that cannot be loaded."""

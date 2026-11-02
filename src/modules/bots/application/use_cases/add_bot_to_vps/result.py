"""`EPIC-047E` — what `AddBotToVpsCommand` answers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AddedToVps:
    """The host created the bot, a DRAFT, and says so in its words; `host_bot_id` is the id it gave."""

    bot_name: str
    host_bot_id: str
    message: str


@dataclass(frozen=True, slots=True)
class NotAddedToVps:
    """Nothing was created, or the host did not say. `unknown` is set when the request went out and no reply came
    in time: the host may still have created the bot, so the person reads the VPS tab before sending it again."""

    bot_name: str
    message: str
    unknown: bool = False


type AddToVpsResult = AddedToVps | NotAddedToVps

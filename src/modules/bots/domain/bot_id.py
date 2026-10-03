"""`EPIC-029B` — a bot's identity, and the tag its orders will carry (ADR D2, D5).

Six characters of `[a-z0-9]`: the same string becomes the `{tag6}` of the
client order id `SEW-{tag6}-{hex10}` that trading generates for the bot's orders
(ADR D5, built in `EPIC-029A`). Binance allows 36 characters in a client order
id; `SEW-` + 6 + `-` + 10 is 21 of them, so the id fits with room to spare, and
lower case plus digits is a subset of the characters Binance accepts.

Generation is random (`secrets`), not sequential: an id leaves the app inside an
order id, and a counter would collide across two installations trading on one
account. Uniqueness inside one store is the creating use case's job — it retries
on a collision (`create_bot/handler.py`), because only the store knows which ids
are taken.
"""

from __future__ import annotations

import re
import secrets
import string
from dataclasses import dataclass

BOT_ID_LENGTH = 6
BOT_ID_ALPHABET = string.ascii_lowercase + string.digits
_BOT_ID_PATTERN = re.compile(rf"^[a-z0-9]{{{BOT_ID_LENGTH}}}$")


class InvalidBotIdError(ValueError):
    """A string that is not six characters of `[a-z0-9]` was offered as a bot id."""


@dataclass(frozen=True, slots=True)
class BotId:
    """The bot's stable identity: its file name, its lease owner and its order tag."""

    value: str

    def __post_init__(self) -> None:
        if not _BOT_ID_PATTERN.fullmatch(self.value):
            raise InvalidBotIdError(
                f"A bot id is {BOT_ID_LENGTH} characters of [a-z0-9], got {self.value!r}"
            )

    def __str__(self) -> str:
        return self.value


class BotIdGenerator:
    """Draws a fresh random `BotId`.

    A class rather than a free function so the creating use case can receive it
    by injection, and a test can hand it a generator that repeats an id to prove
    the collision retry.
    """

    def next_id(self) -> BotId:
        return BotId(
            "".join(secrets.choice(BOT_ID_ALPHABET) for _ in range(BOT_ID_LENGTH))
        )

"""`EPIC-034H` — the Connect step's answer, as the readiness assessment takes it.

Published here (`EPIC-048B`) because both sides hold it: the Start path builds it from a fresh
read of the account, and the Bots screen builds it from what its Connect step answered and
hands it to the assessment through `AssessBotQuery`, so the screen imports no application
internal (`architecture-rule.md` §3.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
)


class ConnectionState(str, Enum):
    READING = "READING"
    FAILED = "FAILED"
    CONNECTED = "CONNECTED"


@dataclass(frozen=True, slots=True)
class ConnectionRead:
    """The Connect step's answer, as the assessment needs it."""

    state: ConnectionState
    #: The venue by its title, never its identifier.
    venue_title: str
    #: What a connected account says about money and permission.
    account: AccountView | None = None
    #: Why a failed read failed, and what to do, without how to read again.
    reason: str = ""

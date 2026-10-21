"""A command on its way to the host, and what the host recorded about it (`EPIC-038J`).

The wire form is one small JSON document, `sew.host-command/1` (`application/host_command_codec.py`).
Here are the values the host and the audit share. A command carries its own identity
(`command_id`, 32 hex characters chosen by the sender) and the moment it was written: the
first is the idempotency key, the second lets the host refuse a file that sat for hours.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)

#: The schema string a command document must carry.
HOST_COMMAND_SCHEMA = "sew.host-command/1"
#: A file larger than this is not a command.
MAX_COMMAND_BYTES = 4096
#: How old a command may be when the host reads it, and how far ahead of the host's clock.
COMMAND_MAX_AGE_S = 300
COMMAND_MAX_SKEW_S = 60


@dataclass(frozen=True, slots=True)
class HostCommand:
    command_id: str
    action: HostControlAction
    bot_id: str
    confirmed_venue: str | None
    issued_at: datetime
    #: A stop that closes the position at market (`BUG-224`); absent from older files.
    close_position: bool = False
    #: The `--set key=value` of an edit (`EPIC-038L`); absent from older files and from every other action.
    settings: tuple[ParameterSetting, ...] = ()
    #: The bot an add creates (`EPIC-045A`); absent from older files and from every other action.
    entry: NewBotEntry | None = None
    #: The venue a move goes to (`EPIC-045G`); absent from older files and from every other action.
    to_venue: str | None = None


class ControlVerdict(StrEnum):
    """What the audit says happened to a command id. `RECEIVED` is the only non-final one."""

    #: Written before the dispatch, so a crash after it can never repeat the command.
    RECEIVED = "received"
    EXECUTED = "executed"
    #: The bot's own command refused (the screen's words are the message).
    REFUSED = "refused"
    #: The command handler raised; the message names the exception type only.
    FAILED = "failed"
    MALFORMED = "malformed"
    UNAUTHORISED = "unauthorised"
    REPLAYED = "replayed"
    EXPIRED = "expired"

    @property
    def is_final(self) -> bool:
        return self is not ControlVerdict.RECEIVED


@dataclass(frozen=True, slots=True)
class ControlAuditEntry:
    """One line of the audit. Holds no secret: ids, an action, a sentence."""

    command_id: str
    at: datetime
    verdict: ControlVerdict
    action: str = ""
    bot_id: str = ""
    message: str = ""

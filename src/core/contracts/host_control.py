"""Ask a running host to stop, pause, resume, start, edit, add or delete one bot (`EPIC-038J`, `EPIC-038K`, `EPIC-038L`, `EPIC-045`, decision O4, channel A).

@details The `bot` command belongs to `bots`, and the thing that carries a request to the
host belongs to `operations`, which depends on `bots`; a verb therefore cannot import its
transport. What crosses is a request, the reply, and the port (`i_host_control.py`). The
transport behind it is a directory the host reads (`operations/adapters/directory_host_control.py`);
a verb does not know that.

A request names an action and a bot and nothing else (an edit adds the settings, which are what
it changes): there is no way here to say *how* to stop. The host answers each action with the command the Bots tab dispatches, and the
answer, including a refusal in the screen's own words, comes back as a reply.

The port that carries a request is `i_host_control.py`.

@par Extension cases
  · a new verb (`bot archive`) - one `HostControlAction` member, and the host's table of
    commands gains the row; the port, the reply and the transport do not change. `START`
    (`EPIC-038K`) was added this way: an older host reads the new word as a malformed document
    and refuses it without effect. `EDIT` (`EPIC-038L`) also adds the optional `settings`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)


class HostControlAction(StrEnum):
    """What the operator asks of one bot. The value is the word on the wire and on the command line."""

    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    #: `EPIC-038K`: start a DRAFT or STOPPED bot, once, as the Bots tab's Start does.
    START = "start"
    #: `EPIC-038L`: change the parameters of a DRAFT or STOPPED bot, as the Bots tab's Save does.
    EDIT = "edit"
    #: `EPIC-045A`: create one DRAFT bot from a plan entry, as the Bots tab's New bot does. It names
    #: no existing bot: `bot_id` is the fixed word `ADD_SUBJECT`, and the entry travels in `entry`.
    ADD = "add"
    #: `EPIC-045B`: forget a DRAFT or STOPPED bot that holds nothing, as the Bots tab's Delete does.
    DELETE = "delete"
    #: `EPIC-045G`: move a DRAFT that never ran to another Spot venue, as the Bots tab's Venue field does.
    #: The target travels in `to_venue`; the bot keeps its id.
    MOVE = "move"
    #: `EPIC-026L`: the owner accepts the account-level loss and lets bots start again. It names no
    #: bot: `bot_id` is the fixed word `LOSS_CAP_SUBJECT`.
    ACKNOWLEDGE_LOSS_CAP = "loss-cap-ack"


#: What an acknowledgement's `bot_id` says: it is about the account, not a bot.
LOSS_CAP_SUBJECT = "loss-cap"
#: What an add's `bot_id` says: the bot does not exist yet, the host gives it its id.
ADD_SUBJECT = "new-bot"


class HostControlStatus(StrEnum):
    """How a request ended, from the operator's side."""

    #: The host ran the bot's own command and it accepted. A stop is asynchronous: the bot is
    #: STOPPING and becomes STOPPED once the exchange confirms no order of its remains.
    DONE = "done"
    #: The host ran the command and the bot's own gate said no (not found, invalid transition,
    #: real money not confirmed...). The words are the screen's.
    REFUSED = "refused"
    #: The host refused the request itself: unauthorised, malformed, replayed, expired, or failed.
    REJECTED = "rejected"
    #: No copy holds the data root, so nothing was written and nothing changed.
    NOT_RUNNING = "not_running"
    #: The host offers no control to this account (no directory, or one that is not owner-only).
    NO_CONTROL = "no_control"
    #: A host holds the data root and recorded no outcome in time; see `HostControlReply.message`.
    NO_ANSWER = "no_answer"


@dataclass(frozen=True, slots=True)
class HostControlRequest:
    """One action on one bot. `confirmed_venue` is the operator's typed answer to the
    real-money question (decision O8), where the bot's own command asks it (stop, resume, start). `close_position` is
    the operator's `--close-position` on a stop: close what the bot holds at market (`BUG-224`).
    `settings` are the `--set key=value` of an edit (`EPIC-038L`); empty for every other action.
    `entry` is the bot an add creates (`EPIC-045A`); `None` for every other action. `to_venue` is the venue
    a move goes to (`EPIC-045G`); `None` for every other action."""

    action: HostControlAction
    bot_id: str
    confirmed_venue: str | None = None
    close_position: bool = False
    settings: tuple[ParameterSetting, ...] = ()
    entry: NewBotEntry | None = None
    to_venue: str | None = None


@dataclass(frozen=True, slots=True)
class HostControlReply:
    """The outcome and a sentence for the operator. `command_id` is empty when nothing was written."""

    status: HostControlStatus
    message: str
    command_id: str = ""
    #: The bot the host's answer is about: for an add, the id the host chose (`EPIC-045A`); otherwise
    #: the bot the request named. Empty when nothing was written.
    bot_id: str = ""

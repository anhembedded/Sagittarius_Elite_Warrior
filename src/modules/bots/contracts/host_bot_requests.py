"""What the `run` host asks of the bots (`EPIC-038D`).

`operations` may import another context only through its `contracts/`, and the
commands the Bots tab dispatches (`StartBotCommand`, `StopBotCommand`) are
application types. The host therefore asks in two contract commands, and the
bots module answers each by dispatching the very command the screen dispatches:
the host adds no way to start or stop a bot, only a way to ask for one by name.

Both answer a `BotCommandResult`, so a refusal reaches the host with the words
the screen would show. `EPIC-038J` adds two more of the same kind, pause and resume, for the
commands a person sends to the running host; `EPIC-038K` reaches `StartBotForHostCommand`, already here, from the command directory too; `EPIC-038L` adds `EditBotForHostCommand`.

@par `StartBotForHostCommand.confirmed_venue` (decision O8)
The screen asks the question that names real money. A command line cannot ask,
so it carries the answer in advance: the operator types the venue
(`--confirm-venue spot_mainnet`), and the start is allowed only if what was typed
equals the bot's venue. A command copied from a testnet run cannot start a
mainnet bot.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)


@dataclass(frozen=True, slots=True)
class StopBotForHostCommand:
    """Stop this bot. By default the base asset it holds is kept (the stop is for maintenance,
    not for selling); `exposure` says otherwise only for a person's explicit close (`BUG-224`)."""

    bot_id: str
    exposure: ExposureHandling = ExposureHandling.KEEP


@dataclass(frozen=True, slots=True)
class StopBotForOperatorCommand:
    """A person's `bot stop` on the running host (`EPIC-038J`, decision O4 follow-up "B"):
    `StopBotForHostCommand`, after opening the venue's order session if it is closed.

    The host's own shutdown stop (`--on-stop stop-bots`) never opens a session: an automated
    caller must not undo an Emergency Stop. A person who types `bot stop` is a deliberate action,
    as Start and Resume are, and a Stop that waits for a session nobody opens never ends. On a
    mainnet venue that opening uses real money's session, so `confirmed_venue` is what the
    operator typed (decision O8); it is asked only when the session is closed.
    """

    bot_id: str
    confirmed_venue: str | None = None
    #: The operator typed `--close-position`: the stop closes what the bot holds at market, as
    #: the screen's "Close the position at market" does. A position venue's stop is refused
    #: without it, because a position left standing has no stop on the exchange (`BUG-224`).
    close_position: bool = False


@dataclass(frozen=True, slots=True)
class PauseBotForHostCommand:
    """Pause this bot (`EPIC-038J`): it stops placing orders, its resting orders stay."""

    bot_id: str


@dataclass(frozen=True, slots=True)
class ResumeBotForHostCommand:
    """Resume this bot, which is PAUSED or RECOVERING (`EPIC-038J`).

    A HALTED bot is refused: its resume proposes a ladder that a person reads and confirms
    (decision D13), and a file cannot. `confirmed_venue` is what the operator typed, judged
    for a RECOVERING mainnet bot, whose resume reopens the order session (decision O8).
    """

    bot_id: str
    confirmed_venue: str | None = None


@dataclass(frozen=True, slots=True)
class StartBotForHostCommand:
    """Start this bot, which is at rest (DRAFT or STOPPED). `confirmed_venue` is what the operator
    typed. Used by `run --start-planned` and, since `EPIC-038K`, by `bot start` on the running host."""

    bot_id: str
    confirmed_venue: str | None = None


@dataclass(frozen=True, slots=True)
class EditBotForHostCommand:
    """Change these parameters of this bot, which is at rest (DRAFT or STOPPED) (`EPIC-038L`).

    A setting names a parameter and the text to store; every other parameter keeps its value. An
    edit places no order and asks no venue (decision O8 is the question at `bot start`, which is
    untouched): the bot lands on DRAFT, as after the Bots tab's Save, and starts only by a Start.
    """

    bot_id: str
    settings: tuple[ParameterSetting, ...]


@dataclass(frozen=True, slots=True)
class ResumeRecoveringForHostCommand:
    """Open the order session of every venue that holds a RECOVERING bot (decision O2).

    A restart leaves RUNNING and PAUSED bots RECOVERING until a deliberate action
    opens the venue's order session, which reconciles each bot against the exchange.
    On the screen that action is the first Start, Arm or order; here it is this
    command, and nothing else - it starts no bot and places no order. A mainnet
    venue is opened only when `confirmed_venue` names it (decision O8).
    """

    confirmed_venue: str | None = None


@dataclass(frozen=True, slots=True)
class VenueResumeOutcome:
    """What opening one venue's session came to."""

    venue: str
    #: The RECOVERING bots on this venue that the open reconciles.
    bot_ids: tuple[str, ...]
    opened: bool
    #: Why it did not open, in the words the session gave; empty when it did.
    note: str = ""


@dataclass(frozen=True, slots=True)
class ResumeRecoveringResult:
    """One outcome per venue that held a RECOVERING bot; empty when none did."""

    venues: tuple[VenueResumeOutcome, ...] = ()


@dataclass(frozen=True, slots=True)
class ResumeHaltedForHostCommand:
    """Resume every bot that is HALTED or AWAITING_RECOVERY, as a person's Resume and Confirm
    would (`EPIC-042E`, decision D13).

    The Resume is the screen's own `ResumeBotCommand`, so the exchange's facts are read, the
    order session is opened and the ladder is the one the screen would propose; the Confirm is
    the screen's own `ConfirmBotResumeCommand`, sent once the bot holds the proposal. A bot on
    a mainnet venue is resumed only when `confirmed_venue` names its venue (decision O8); no
    other state is touched.
    """

    confirmed_venue: str | None = None


@dataclass(frozen=True, slots=True)
class HaltedBotResumeOutcome:
    """What the host's resume of one bot came to."""

    bot_id: str
    venue: str
    #: The state the bot was in when the host asked (`HALTED` or `AWAITING_RECOVERY`).
    was: str
    #: The confirmation was accepted: the bot's worker lays the ladder and the bot leaves its state.
    resumed: bool
    #: Why it was not resumed, in the words the refusal gave; empty when it was.
    note: str = ""


@dataclass(frozen=True, slots=True)
class ResumeHaltedResult:
    """One outcome per bot that was HALTED or AWAITING_RECOVERY; empty when none was."""

    bots: tuple[HaltedBotResumeOutcome, ...] = ()

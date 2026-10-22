"""What the `run` host asks of the bots (`EPIC-038D`).

`operations` may import another context only through its `contracts/`, and the
commands the Bots tab dispatches (`StartBotCommand`, `StopBotCommand`) are
application types. The host therefore asks in two contract commands, and the
bots module answers each by dispatching the very command the screen dispatches:
the host adds no way to start or stop a bot, only a way to ask for one by name.

Both answer a `BotCommandResult`, so a refusal reaches the host with the words
the screen would show. `EPIC-038J` adds two more of the same kind, pause and resume, for the
commands a person sends to the running host; `EPIC-038K` reaches `StartBotForHostCommand`, already here, from the command directory too; `EPIC-038L` adds `EditBotForHostCommand`; `EPIC-045` adds `AddBotForHostCommand` and `DeleteBotForHostCommand`; `EPIC-045G` adds `MoveBotForHostCommand`.

@par `StartBotForHostCommand.confirmed_venue` (decision O8)
The screen asks the question that names real money. A command line cannot ask,
so it carries the answer in advance: the operator types the venue
(`--confirm-venue spot_mainnet`), and the start is allowed only if what was typed
equals the bot's venue. A command copied from a testnet run cannot start a
mainnet bot.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
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
    """Resume this bot, which is PAUSED, RECOVERING, HALTED or AWAITING_RECOVERY (`EPIC-038J`).

    A HALTED or AWAITING_RECOVERY bot's resume only proposes a ladder and places nothing
    (decision D13); `ConfirmBotResumeForHostCommand` is the person's second step (`EPIC-045G`,
    owner decision O1). `confirmed_venue` is what the operator typed, judged for a mainnet bot
    whose resume reopens the order session (decision O8).
    """

    bot_id: str
    confirmed_venue: str | None = None


@dataclass(frozen=True, slots=True)
class ConfirmBotResumeForHostCommand:
    """Lay the ladder this bot's last resume proposed (`EPIC-045G`), as the Bots tab's Confirm resume does.

    `confirmed_venue` is what the operator typed: the confirmation places orders, so a mainnet bot
    needs its venue typed here as well as at the resume (decision O8). `proposal` is the fingerprint
    the resume printed (owner decision O3): the confirmation lays the ladder that was read and no other,
    and a command with none is refused.
    """

    bot_id: str
    confirmed_venue: str | None = None
    proposal: str | None = None


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
class AddBotForHostCommand:
    """Create this bot, as the Bots tab's New bot does (`EPIC-045A`): a DRAFT, saved and not started.

    An add places no order and asks no venue; the bot starts only by a Start, whose real-money
    question (decision O8) is untouched. `entry` is text in a closed shape (`NewBotEntry`); the
    handler judges whether the kind, the venue and the parameters are ones this build can store.
    """

    entry: NewBotEntry


@dataclass(frozen=True, slots=True)
class DeleteBotForHostCommand:
    """Forget this bot, which is at rest (DRAFT or STOPPED) and holds nothing (`EPIC-045B`).

    The Bots tab's Delete, plus one refusal the tab does not make: a bot whose record still shows a
    held base, a live order or an order it owes is kept, because a host delete has no dialog
    to say "nothing is sent to the exchange" to a person. Sends nothing to the exchange.
    """

    bot_id: str


@dataclass(frozen=True, slots=True)
class MoveBotForHostCommand:
    """Move this bot, a DRAFT that never ran, to another Spot venue (`EPIC-045G`).

    The Bots tab's Venue field. `venue` is the `TradingVenue` word. The move places no order and asks no
    venue (decision O8 is the question at `bot start`); the bot keeps its id and stays DRAFT.
    """

    bot_id: str
    venue: str


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


@dataclass(frozen=True, slots=True)
class AcknowledgeLossCapForHostCommand:
    """The owner's `bot loss-cap-ack` (`EPIC-026L`): clear the latched account-level loss cap so
    bots may start again. It clears the trip and nothing else - no bot is started or resumed by
    it - and the day's count is not reset, so it is refused while today's loss is still at or
    above the figure, and the cap trips again at the figure unless the owner raised it."""


@dataclass(frozen=True, slots=True)
class ArmStrategyForHostCommand:
    """The operator's `bot arm-strategy` (`EPIC-045G`): arm a venue's saved strategy arming, as the Bots tab's
    Arm strategy does with the form it filled from that same saved arming.

    `venue` is the venue word to arm on. The arming's strategy, symbol, interval, sizing, leverage and
    parameters are the saved ones and are never typed on a command line. A strategy places orders on its own
    once armed, so on a mainnet venue `confirmed_venue` must be that venue (decision O8, owner decision O2).
    """

    venue: str
    confirmed_venue: str | None = None


@dataclass(frozen=True, slots=True)
class DisarmStrategyForHostCommand:
    """The operator's `bot disarm-strategy` (`EPIC-045G`): remove a venue's armed strategy, as the Bots tab's
    Disarm strategy does. It sells and cancels nothing, so it asks no venue confirmation; a position open on the
    strategy's symbol refuses it, in words."""

    venue: str


@dataclass(frozen=True, slots=True)
class ApplyPlanEntryForHostCommand:
    """The operator's `bot apply`, one entry at a time, beside a running host (`EPIC-045C`).

    The host carries the entry out as the offline apply does (create a DRAFT, edit, or leave) and records
    `desired_state` (`running` or `stopped`); it never starts the bot. The entry is judged again on the host as a
    plan entry, because a command file is a trust boundary.
    """

    entry: NewBotEntry
    desired_state: str


@dataclass(frozen=True, slots=True)
class UnplanBotForHostCommand:
    """The operator's `bot apply`, for a bot the plan no longer names (`EPIC-045C`): forget its recorded wish, so
    `run --start-planned` stops acting on it. The bot itself is not touched."""

    bot_id: str

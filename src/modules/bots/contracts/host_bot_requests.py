"""What the `run` host asks of the bots (`EPIC-038D`).

`operations` may import another context only through its `contracts/`, and the
commands the Bots tab dispatches (`StartBotCommand`, `StopBotCommand`) are
application types. The host therefore asks in two contract commands, and the
bots module answers each by dispatching the very command the screen dispatches:
the host adds no way to start or stop a bot, only a way to ask for one by name.

Both answer a `BotCommandResult`, so a refusal reaches the host with the words
the screen would show.

@par `StartBotForHostCommand.confirmed_venue` (decision O8)
The screen asks the question that names real money. A command line cannot ask,
so it carries the answer in advance: the operator types the venue
(`--confirm-venue spot_mainnet`), and the start is allowed only if what was typed
equals the bot's venue. A command copied from a testnet run cannot start a
mainnet bot.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StopBotForHostCommand:
    """Stop this bot, keeping the base asset it holds (the stop is for maintenance,
    not for selling)."""

    bot_id: str


@dataclass(frozen=True, slots=True)
class StartBotForHostCommand:
    """Start this bot, which is at rest. `confirmed_venue` is what the operator typed."""

    bot_id: str
    confirmed_venue: str | None = None


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

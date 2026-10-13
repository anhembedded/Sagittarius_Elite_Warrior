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

"""`EPIC-038C` — the one read model of "what are my bots doing", for anything that is not the Bots tab.

The `bot list` and `bot show` commands, `status`, and (when they exist) the
health strip of `EPIC-035W` and the heartbeat of `EPIC-036E` read this one
report, so they cannot disagree about a bot. It is built by one query
(`GetBotStatusReportQuery`) from the results of the Bots tab's own queries
(`ListBotsQuery`, `GetBotQuery`); nothing reads a bot file but the store behind
those.

Plain, frozen and JSON-ready: a script's `--json` is `payload()` of this report,
so a field here is a field in the contract with scripts. It holds no account
balance, no profit and no credential (`test_the_status_payloads_hold_no_secret`).

@par `state` is a record, not a measurement
Bot states come from the bots' files. While a copy of the app is running they are
kept current; with none running they are what the last copy left, so a bot can
read `RUNNING` and trade nowhere. `app_running` says which of the two a reader
holds, and the text views say so in words.

@par `health` stays empty until `EPIC-035W` exists
and then carries that task's per-bot snapshot unchanged, under whatever keys it
defines. `status` does not interpret it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue

#: The `state` of a bot whose file this build cannot read. Not a lifecycle
#: state: the bot may well be running, and the file is the only record of it.
UNREADABLE_STATE = "unreadable"

#: The states in which a bot has nothing on the exchange and nothing to watch
#: (`RunningBotsObjection`'s `_AT_REST`, spelled as the report spells states).
#: `test_the_at_rest_states_are_the_lifecycles` ties the two together.
AT_REST_STATES = frozenset({"DRAFT", "STOPPED"})

#: Said above any list of states when no copy of the app is running.
RECORDED_STATES_NOTE = (
    "No copy of the app is running: these are the states recorded in the bot "
    "files, not live (a bot shown as RUNNING is running nowhere)."
)


@dataclass(frozen=True, slots=True)
class GetBotStatusReportQuery:
    """Every bot, or just `bot_id` when one is named."""

    bot_id: str | None = None


@dataclass(frozen=True, slots=True)
class BotStatusEntry:
    """One readable bot."""

    bot_id: str
    name: str
    kind: str
    venue: str
    symbol: str
    #: A lifecycle state's value (`RUNNING`, `HALTED`, ...).
    state: str
    #: Why the bot halted, stopped or exited; empty when nothing did.
    reason: str
    run_started_at: datetime | None
    health: Mapping[str, JsonValue] = field(default_factory=dict)
    #: How many orders the bot's own record says rest on the exchange; `None`
    #: when it keeps no record (a draft, a bot that never ran). The bot's account,
    #: not a safety input (`BotProgress`): the host reads it to say what a stop leaves.
    resting_orders: int | None = None
    #: Whether a restart makes this bot RECOVERING (RUNNING, PAUSED or RECOVERING), asked of
    #: the lifecycle table. The host judges a mainnet resume by it *before* the app boots,
    #: when a RUNNING bot on disk is still RUNNING and not yet RECOVERING.
    recovers_on_restart: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "health", MappingProxyType(dict(self.health)))

    @property
    def is_at_rest(self) -> bool:
        return self.state in AT_REST_STATES

    def payload(self) -> dict[str, JsonValue]:
        return {
            "bot_id": self.bot_id,
            "name": self.name,
            "kind": self.kind,
            "venue": self.venue,
            "symbol": self.symbol,
            "state": self.state,
            "reason": self.reason,
            "run_started_at": _utc(self.run_started_at),
            "health": dict(self.health),
            "resting_orders": self.resting_orders,
            "recovers_on_restart": self.recovers_on_restart,
        }


@dataclass(frozen=True, slots=True)
class UnreadableBotEntry:
    """A bot file this build refused to load, named with where it is."""

    bot_id: str
    path: str
    reason: str
    state: str = UNREADABLE_STATE

    def payload(self) -> dict[str, JsonValue]:
        return {
            "bot_id": self.bot_id,
            "state": self.state,
            "path": self.path,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class BotStatusReport:
    """Bots oldest first, then the files that would not load."""

    bots: tuple[BotStatusEntry, ...] = ()
    unreadable: tuple[UnreadableBotEntry, ...] = ()
    #: Whether some copy of the app holds the data root. When it is `False` the
    #: `state` of every bot is only what its file *recorded* when the last copy
    #: stopped (a bot may say `RUNNING` and be running nowhere); a reader that
    #: acts on `state` must read this first.
    app_running: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.bots and not self.unreadable

    def state_counts(self) -> dict[str, int]:
        """`state -> how many`, unreadable files counted under `unreadable`."""
        counts: dict[str, int] = {}
        for bot in self.bots:
            counts[bot.state] = counts.get(bot.state, 0) + 1
        if self.unreadable:
            counts[UNREADABLE_STATE] = len(self.unreadable)
        return counts

    def payload(self) -> dict[str, JsonValue]:
        return {
            "app_running": self.app_running,
            "bots": [bot.payload() for bot in self.bots],
            "unreadable": [bot.payload() for bot in self.unreadable],
        }


def _utc(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

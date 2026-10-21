"""What the heartbeat and the daily summary say (`EPIC-036E`).

Pure functions over the bots' status report (`EPIC-038C`, the one read model the Bots tab,
`status` and these messages share) and the outbox's counts. Nothing is measured here: a figure
the report does not carry is not printed, and the report's `health` slot (filled by `EPIC-035W`)
is shown exactly as it comes, so a screen and this message cannot disagree.

**The lines that matter come first.** A channel cuts a long message from the end (Discord at
2000 characters, the head and the time stamp included), so the counts, the unreadable files and
the alert counts are written before the per-bot lines, and those are added while they fit
(`MAX_DETAIL`) and counted when they do not.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import GridLadder
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder_texts import (
    waiting_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    plain_price,
)

#: The detail stays under this many characters: Discord refuses more than 2000 in a message and
#: the head, the subject and the time stamp take about two hundred of them.
MAX_DETAIL = 1700

#: The state of a bot waiting for its range, as the status report spells states (alerting reads
#: `bots.contracts`, not `bots.domain`); `test_the_heartbeat_names_a_bot_waiting_for_its_range` spells it from the enum.
_AWAITING_RANGE = "AWAITING_RANGE"

#: The scheduled messages themselves are not "alerts of the day".
_NOT_COUNTED = frozenset({AlertKind.HEARTBEAT, AlertKind.DAILY_SUMMARY})


def unreadable_report_text(error: Exception) -> str:
    """Only the type: the message of an error can carry a path or a request. The error itself
    is in the run log (`HeartbeatService`)."""
    return (
        "The app is running, but the bots' state could not be read "
        f"({type(error).__name__}); see the run log."
    )


def counts_line(report: BotStatusReport) -> str:
    counts = report.state_counts()
    if not counts:
        return "No bot is configured."
    parts = ", ".join(f"{count} {state}" for state, count in sorted(counts.items()))
    return f"{sum(counts.values())} bot(s): {parts}."


def heartbeat_text(report: BotStatusReport) -> str:
    head = ["The app is running.", counts_line(report), *_unreadable_lines(report)]
    active = [bot for bot in report.bots if not bot.is_at_rest]
    return _with_listing(head, [_bot_line(bot) for bot in active])


def summary_text(
    report: BotStatusReport, counts: Mapping[AlertKind, int], window: timedelta
) -> str:
    head = [
        counts_line(report),
        *_unreadable_lines(report),
        _alerts_line(counts, window),
    ]
    earning = [_earnings_line(bot) for bot in report.bots if bot.earnings is not None]
    return _with_listing(head, earning)


def _unreadable_lines(report: BotStatusReport) -> list[str]:
    if not report.unreadable:
        return []
    return [f"{len(report.unreadable)} bot file(s) could not be read."]


def _with_listing(head: list[str], listing: Iterable[str]) -> str:
    """`head`, then as many of `listing` as fit under `MAX_DETAIL`, then how many did not."""
    lines = list(head)
    size = len("\n".join(lines))
    items = list(listing)
    room = MAX_DETAIL - len(_more_line(len(items)))
    shown = 0
    for line in items:
        if size + 1 + len(line) > room:
            break
        lines.append(line)
        size += 1 + len(line)
        shown += 1
    if shown < len(items):
        lines.append(_more_line(len(items) - shown))
    return "\n".join(lines)


def _more_line(count: int) -> str:
    return f"... and {count} more"


def _bot_line(bot: BotStatusEntry) -> str:
    where = f"{bot.symbol}, {bot.venue}".strip(", ")
    why = bot.reason or _waiting_for(bot)
    state = bot.state if not why else f"{bot.state} - {why}"
    parts = [f"- {bot.name} ({where}): {state}"]
    if bot.resting_orders:
        parts.append(f"{bot.resting_orders} resting orders")
    if bot.health:
        parts.append(" ".join(f"{key}={value}" for key, value in bot.health.items()))
    return "; ".join(parts)


def _waiting_for(bot: BotStatusEntry) -> str:
    """A bot waiting for its range says which range and at which price (`EPIC-044C`)."""
    ladder = bot.ladder
    if bot.state != _AWAITING_RANGE or not isinstance(ladder, GridLadder):
        return ""
    return waiting_text(ladder.position, plain_price)


def _earnings_line(bot: BotStatusEntry) -> str:
    earnings = bot.earnings
    if earnings is None:
        return f"- {bot.name} ({bot.symbol}): no earnings recorded"
    total = (
        "total PnL not priced yet"
        if earnings.total_pnl is None
        else f"total PnL {earnings.total_pnl}"
    )
    return (
        f"- {bot.name} ({bot.symbol}): grid profit {earnings.grid_profit} over "
        f"{earnings.completed_cycles} cycles, {total}"
    )


def _alerts_line(counts: Mapping[AlertKind, int], window: timedelta) -> str:
    hours = int(window.total_seconds() // 3600)
    counted = {
        kind.name: count for kind, count in counts.items() if kind not in _NOT_COUNTED
    }
    if not counted:
        return f"No alerts in the last {hours} h."
    listing = ", ".join(f"{kind} x{count}" for kind, count in sorted(counted.items()))
    return f"Alerts in the last {hours} h: {listing}."

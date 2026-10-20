"""What the heartbeat and the daily summary say (`EPIC-036E`).

Pure functions over the bots' status report (`EPIC-038C`, the one read model the Bots tab,
`status` and these messages share) and the outbox's history. Nothing is measured here: a figure
the report does not carry is not printed, and the report's `health` slot (filled by `EPIC-035W`)
is shown exactly as it comes, so a screen and this message cannot disagree.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    HistoryEntry,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    RunEarnings,
)

#: The summary lists this many bots and counts the rest.
MAX_BOTS_LISTED = 25

#: The scheduled messages themselves are not "alerts of the day".
_NOT_COUNTED = frozenset({AlertKind.HEARTBEAT, AlertKind.DAILY_SUMMARY})


def unreadable_report_text(error: Exception) -> str:
    """Only the type: the message of an error can carry a path or a request."""
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
    lines = ["The app is running.", counts_line(report)]
    active = [bot for bot in report.bots if not bot.is_at_rest]
    lines.extend(_bot_line(bot) for bot in active[:MAX_BOTS_LISTED])
    if len(active) > MAX_BOTS_LISTED:
        lines.append(f"... and {len(active) - MAX_BOTS_LISTED} more")
    if report.unreadable:
        lines.append(f"{len(report.unreadable)} bot file(s) could not be read.")
    return "\n".join(lines)


def summary_text(
    report: BotStatusReport,
    history: Sequence[HistoryEntry],
    now: datetime,
    window: timedelta,
) -> str:
    lines = [counts_line(report)]
    earning = [(bot, bot.earnings) for bot in report.bots if bot.earnings is not None]
    lines.extend(
        _earnings_line(bot, earnings) for bot, earnings in earning[:MAX_BOTS_LISTED]
    )
    if len(earning) > MAX_BOTS_LISTED:
        lines.append(f"... and {len(earning) - MAX_BOTS_LISTED} more")
    if report.unreadable:
        lines.append(f"{len(report.unreadable)} bot file(s) could not be read.")
    lines.append(_alerts_line(history, now, window))
    return "\n".join(lines)


def _bot_line(bot: BotStatusEntry) -> str:
    where = f"{bot.symbol}, {bot.venue}".strip(", ")
    state = bot.state if not bot.reason else f"{bot.state} - {bot.reason}"
    parts = [f"- {bot.name} ({where}): {state}"]
    if bot.resting_orders:
        parts.append(f"{bot.resting_orders} resting orders")
    if bot.health:
        parts.append(" ".join(f"{key}={value}" for key, value in bot.health.items()))
    return "; ".join(parts)


def _earnings_line(bot: BotStatusEntry, earnings: RunEarnings) -> str:
    total = (
        "total PnL not priced yet"
        if earnings.total_pnl is None
        else f"total PnL {earnings.total_pnl}"
    )
    return (
        f"- {bot.name} ({bot.symbol}): grid profit {earnings.grid_profit} over "
        f"{earnings.completed_cycles} cycles, {total}"
    )


def _alerts_line(
    history: Sequence[HistoryEntry], now: datetime, window: timedelta
) -> str:
    counted: dict[str, int] = {}
    for entry in history:
        alert = entry.record.alert
        if alert.kind in _NOT_COUNTED or entry.record.last_at < now - window:
            continue
        counted[alert.kind.name] = counted.get(alert.kind.name, 0) + entry.record.count
    hours = int(window.total_seconds() // 3600)
    if not counted:
        return f"No alerts in the last {hours} h."
    listing = ", ".join(f"{kind} x{count}" for kind, count in sorted(counted.items()))
    return f"Alerts in the last {hours} h: {listing}."

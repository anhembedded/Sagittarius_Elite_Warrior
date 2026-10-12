"""`EPIC-038C` — `bot list` and `bot show` as `Report`s.

Both are built from `BotStatusReport` once; `--json` and the text view come from
the same report, so they cannot disagree. The payload's keys are the contract
with scripts (`test_the_bot_report_payload_keys_are_pinned`): a field is added
within a version, never renamed.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    JsonValue,
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
    UnreadableBotEntry,
)

LIST_COMMAND = "bot-list"
SHOW_COMMAND = "bot-show"
SCHEMA_VERSION = 1

_NAME_WIDTH = 24
_STATE_WIDTH = 10


def bot_list_report(status: BotStatusReport) -> Report:
    payload: dict[str, JsonValue] = {
        **status.payload(),
        "counts": dict(status.state_counts()),
    }
    return Report(LIST_COMMAND, SCHEMA_VERSION, payload, _list_layout(status))


def bot_show_report(status: BotStatusReport) -> Report:
    """One bot (the report holds the one the id named)."""
    return Report(SHOW_COMMAND, SCHEMA_VERSION, status.payload(), _show_layout(status))


def _list_layout(status: BotStatusReport) -> tuple[ReportSection, ...]:
    if status.is_empty:
        return (ReportSection(None, (ReportRow.of("No bots."),)),)
    rows = [
        _row("ID", "NAME", "STATE", "VENUE", "SYMBOL", "REASON"),
        *(_bot_row(bot) for bot in status.bots),
        *(_unreadable_row(bot) for bot in status.unreadable),
    ]
    return (ReportSection(None, tuple(rows)),)


def _show_layout(status: BotStatusReport) -> tuple[ReportSection, ...]:
    sections = [_bot_section(bot) for bot in status.bots]
    sections += [_unreadable_section(bot) for bot in status.unreadable]
    return tuple(sections)


def _row(
    bot_id: str, name: str, state: str, venue: str, symbol: str, reason: str
) -> ReportRow:
    return ReportRow(
        (
            ReportCell(bot_id, 6),
            ReportCell(name, _NAME_WIDTH),
            ReportCell(state, _STATE_WIDTH),
            ReportCell(venue, 14),
            ReportCell(symbol, 10),
            ReportCell(reason),
        )
    )


def _bot_row(bot: BotStatusEntry) -> ReportRow:
    return _row(bot.bot_id, bot.name, bot.state, bot.venue, bot.symbol, bot.reason)


def _unreadable_row(bot: UnreadableBotEntry) -> ReportRow:
    return _row(bot.bot_id, "-", bot.state, "-", "-", f"{bot.path}: {bot.reason}")


def _field(label: str, value: str) -> ReportRow:
    return ReportRow((ReportCell(label, 12), ReportCell(value)))


def _bot_section(bot: BotStatusEntry) -> ReportSection:
    return ReportSection(
        f"Bot {bot.bot_id}",
        (
            _field("Name", bot.name),
            _field("Kind", bot.kind),
            _field("State", bot.state),
            _field("Reason", bot.reason or "-"),
            _field("Venue", bot.venue),
            _field("Symbol", bot.symbol),
            _field(
                "Run started",
                bot.run_started_at.isoformat() if bot.run_started_at else "-",
            ),
        ),
    )


def _unreadable_section(bot: UnreadableBotEntry) -> ReportSection:
    return ReportSection(
        f"Bot {bot.bot_id}",
        (
            _field("State", bot.state),
            _field("File", bot.path),
            _field("Why", bot.reason),
        ),
    )

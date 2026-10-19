"""`EPIC-038C` — `bot list` and `bot show` as `Report`s.

Both are built from `BotStatusReport` once; `--json` and the text view come from
the same report, so they cannot disagree. The payload's keys are the contract
with scripts (`test_the_bot_report_payload_keys_are_pinned`): a field is added
within a version, never renamed.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    JsonValue,
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    RECORDED_STATES_NOTE,
    BotRecoveryTable,
    BotStatusEntry,
    BotStatusReport,
    RecoveryRuleLine,
    UnreadableBotEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    cycles_text,
    grid_profit_text,
    plain_money,
    plain_price,
    total_pnl_text,
    unrealised_text,
)

LIST_COMMAND = "bot-list"
SHOW_COMMAND = "bot-show"
SCHEMA_VERSION = 1

_NAME_WIDTH = 24
_STATE_WIDTH = 10
#: `BOT-192`: the Bots tab's own figures, as columns of the list.
_EARNINGS_HEADS = ("GRID PROFIT", "CYCLES", "TOTAL PNL")


def _recorded_note(status: BotStatusReport) -> tuple[ReportSection, ...]:
    if status.app_running or status.is_empty:
        return ()
    return (ReportSection(None, (ReportRow.of(RECORDED_STATES_NOTE),)),)


def bot_list_report(status: BotStatusReport) -> Report:
    payload: dict[str, JsonValue] = {
        **status.payload(),
        "counts": dict(status.state_counts()),
    }
    return Report(LIST_COMMAND, SCHEMA_VERSION, payload, _list_layout(status))


def bot_show_report(status: BotStatusReport) -> Report:
    """One bot (the report holds the one the id named)."""
    return Report(SHOW_COMMAND, SCHEMA_VERSION, status.payload(), _show_layout(status))


def bot_show_parameters_report(status: BotStatusReport) -> Report:
    """`bot show --params` (`EPIC-038L`): the same report with the bot's parameters as rows, sorted
    by key, values as stored. The payload is the same (it always carries `parameters`)."""
    return Report(
        SHOW_COMMAND,
        SCHEMA_VERSION,
        status.payload(),
        _show_layout(status, _bot_section_with_parameters),
    )


def _list_layout(status: BotStatusReport) -> tuple[ReportSection, ...]:
    if status.is_empty:
        return (ReportSection(None, (ReportRow.of("No bots."),)),)
    rows = [
        _row("ID", "NAME", "STATE", "VENUE", "SYMBOL", _EARNINGS_HEADS, "REASON"),
        *(_bot_row(bot) for bot in status.bots),
        *(_unreadable_row(bot) for bot in status.unreadable),
    ]
    return (*_recorded_note(status), ReportSection(None, tuple(rows)))


def _show_layout(
    status: BotStatusReport,
    section_of: Callable[[BotStatusEntry], ReportSection] | None = None,
) -> tuple[ReportSection, ...]:
    section_of = section_of or _bot_section
    sections = [section_of(bot) for bot in status.bots]
    sections += [_unreadable_section(bot) for bot in status.unreadable]
    return (*_recorded_note(status), *sections)


def _row(
    bot_id: str,
    name: str,
    state: str,
    venue: str,
    symbol: str,
    earnings: tuple[str, str, str],
    reason: str,
) -> ReportRow:
    return ReportRow(
        (
            ReportCell(bot_id, 6),
            ReportCell(name, _NAME_WIDTH),
            ReportCell(state, _STATE_WIDTH),
            ReportCell(venue, 14),
            ReportCell(symbol, 10),
            *(ReportCell(text, 14) for text in earnings),
            ReportCell(reason),
        )
    )


def _bot_row(bot: BotStatusEntry) -> ReportRow:
    return _row(
        bot.bot_id,
        bot.name,
        bot.state,
        bot.venue,
        bot.symbol,
        (
            grid_profit_text(bot.earnings, plain_money),
            cycles_text(bot.earnings),
            total_pnl_text(bot.earnings, plain_money),
        ),
        bot.reason,
    )


def _unreadable_row(bot: UnreadableBotEntry) -> ReportRow:
    return _row(
        bot.bot_id,
        "-",
        bot.state,
        "-",
        "-",
        ("-", "-", "-"),
        f"{bot.path}: {bot.reason}",
    )


def _field(label: str, value: str) -> ReportRow:
    return ReportRow((ReportCell(label, 12), ReportCell(value)))


def _duration(seconds: int) -> str:
    for unit, size in (("h", 3600), ("min", 60)):
        if seconds % size == 0:
            return f"{seconds // size} {unit}"
    return f"{seconds} s"


def _recovery_rows(table: BotRecoveryTable | None) -> tuple[ReportRow, ...]:
    """`EPIC-042G`: what the bot recovers from by itself, one row per reason."""
    if table is None:
        return ()
    if not table.rules:
        layer = f" ({table.none_decided_by} layer)" if table.none_decided_by else ""
        return (_field("Recovery", f"no automatic recovery{layer}"),)
    return tuple(_recovery_row(rule) for rule in table.rules)


def _recovery_row(rule: RecoveryRuleLine) -> ReportRow:
    return _field(
        "Recovery",
        f"{rule.code}: after {_duration(rule.dwell_s)} clear, "
        f"{rule.attempts_used} of {rule.max_attempts} used in {_duration(rule.window_s)}, "
        f"tells you after {_duration(rule.stalled_after_s)} waiting "
        f"({rule.decided_by} layer)",
    )


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
            _field("Grid profit", grid_profit_text(bot.earnings, plain_money)),
            _field("Cycles", cycles_text(bot.earnings)),
            _field("Total PnL", total_pnl_text(bot.earnings, plain_money)),
            _field(
                "Unrealised",
                unrealised_text(bot.earnings, plain_money, plain_price),
            ),
            *_recovery_rows(bot.recovery),
        ),
    )


def _bot_section_with_parameters(bot: BotStatusEntry) -> ReportSection:
    section = _bot_section(bot)
    held = dict(sorted((bot.parameters or {}).items()))
    rows = tuple(_field(f"param {key}", value) for key, value in held.items()) or (
        _field("Parameters", "none set"),
    )
    return ReportSection(section.title, (*section.rows, *rows))


def _unreadable_section(bot: UnreadableBotEntry) -> ReportSection:
    return ReportSection(
        f"Bot {bot.bot_id}",
        (
            _field("State", bot.state),
            _field("File", bot.path),
            _field("Why", bot.reason),
        ),
    )

"""`EPIC-038C` — `bot list` and `bot show` as `Report`s.

Both are built from `BotStatusReport` once; `--json` and the text view come from
the same report, so they cannot disagree. The payload's keys are the contract
with scripts (`test_the_bot_report_payload_keys_are_pinned`): a field is added
within a version, never renamed.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    JsonValue,
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_exchange_unrealised_rows import (
    exchange_unrealised_rows,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_waiting_reason import (
    reason_cell,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    RECORDED_STATES_NOTE,
    BotRecoveryTable,
    BotStatusEntry,
    BotStatusReport,
    RecoveryRuleLine,
    UnreadableBotEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    GridLadder,
    LadderRow,
    LadderUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder_texts import (
    net_figures_note,
    percent_of,
    position_texts,
    recorded_average_text,
    small_money_text,
    step_text,
    summary_line,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    NO_VALUE,
    TOTAL_PNL_BASIS,
    TOTAL_PNL_HEAD,
    TOTAL_PNL_LEGEND,
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
_EARNINGS_HEADS = ("GRID PROFIT", "CYCLES", TOTAL_PNL_HEAD)
#: `BOT-193`: the ladder's steps, in a word of the Bots tab's Plan row (`Grid step`).
_STEP_HEAD = "GRID STEP"
_STEP_WIDTH = 30


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


def bot_show_grids_report(status: BotStatusReport) -> Report:
    """`bot show --grids` (`BOT-193`): the same report with one row per grid after the bot's rows."""
    return Report(
        SHOW_COMMAND,
        SCHEMA_VERSION,
        status.payload(),
        _show_layout(status, _bot_section, _grids_section),
    )


def bot_show_grids_parameters_report(status: BotStatusReport) -> Report:
    """`bot show --grids --params`: the parameters' rows, then the grids."""
    return Report(
        SHOW_COMMAND,
        SCHEMA_VERSION,
        status.payload(),
        _show_layout(status, _bot_section_with_parameters, _grids_section),
    )


def _list_layout(status: BotStatusReport) -> tuple[ReportSection, ...]:
    if status.is_empty:
        return (ReportSection(None, (ReportRow.of("No bots."),)),)
    rows = [
        _row(
            ("ID", "NAME", "STATE", "VENUE", "SYMBOL"),
            _EARNINGS_HEADS,
            _STEP_HEAD,
            "REASON",
        ),
        *(_bot_row(bot) for bot in status.bots),
        *(_unreadable_row(bot) for bot in status.unreadable),
    ]
    legend = ReportSection(None, (ReportRow.of(TOTAL_PNL_LEGEND),))
    return (
        *_recorded_note(status),
        ReportSection(None, tuple(rows), has_header=True),
        legend,
    )


def _show_layout(
    status: BotStatusReport,
    section_of: Callable[[BotStatusEntry], ReportSection] | None = None,
    after: Callable[[BotStatusEntry], ReportSection] | None = None,
) -> tuple[ReportSection, ...]:
    section_of = section_of or _bot_section
    sections: list[ReportSection] = []
    for bot in status.bots:
        sections.append(section_of(bot))
        if after is not None:
            sections.append(after(bot))
    sections += [_unreadable_section(bot) for bot in status.unreadable]
    return (*_recorded_note(status), *sections)


def _row(
    leading: tuple[str, str, str, str, str],
    earnings: tuple[str, str, str],
    grid_step: str,
    reason: str,
) -> ReportRow:
    """One line of the list: id, name, state, venue, symbol; then the run's earnings; then why."""
    bot_id, name, state, venue, symbol = leading
    grid_profit, cycles, total = earnings
    return ReportRow(
        (
            ReportCell(bot_id, 6),
            ReportCell(name, _NAME_WIDTH),
            ReportCell(state, _STATE_WIDTH),
            ReportCell(venue, 14),
            ReportCell(symbol, 10),
            ReportCell(grid_profit, 14),
            ReportCell(cycles, 8),
            ReportCell(total, 14),
            ReportCell(grid_step, _STEP_WIDTH),
            ReportCell(reason),
        )
    )


def _bot_row(bot: BotStatusEntry) -> ReportRow:
    return _row(
        (bot.bot_id, bot.name, bot.state, bot.venue, bot.symbol),
        (
            grid_profit_text(bot.earnings, plain_money),
            cycles_text(bot.earnings),
            total_pnl_text(bot.earnings, plain_money),
        ),
        _step_cell(bot),
        reason_cell(bot),
    )


def _step_cell(bot: BotStatusEntry) -> str:
    ladder = bot.ladder
    return step_text(ladder.summary) if isinstance(ladder, GridLadder) else NO_VALUE


def _unreadable_row(bot: UnreadableBotEntry) -> ReportRow:
    return _row(
        (bot.bot_id, "-", bot.state, "-", "-"),
        ("-", "-", "-"),
        "-",
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
            _field("Reason", reason_cell(bot) or "-"),
            _field("Venue", bot.venue),
            _field("Symbol", bot.symbol),
            _field(
                "Run started",
                bot.run_started_at.isoformat() if bot.run_started_at else "-",
            ),
            _field("Grid profit", grid_profit_text(bot.earnings, plain_money)),
            _field("Cycles", cycles_text(bot.earnings)),
            _field("Total PnL", total_pnl_text(bot.earnings, plain_money)),
            _field("", f"({TOTAL_PNL_BASIS})"),
            _field(
                "Unrealised",
                unrealised_text(bot.earnings, plain_money, plain_price),
            ),
            *exchange_unrealised_rows(bot),
            *_ladder_rows(bot),
            *_recovery_rows(bot.recovery),
        ),
    )


def _ladder_rows(bot: BotStatusEntry) -> tuple[ReportRow, ...]:
    """`BOT-193`: the ladder in one line, what a completed cycle booked on average, and where the
    last price the bot heard stands; the Bots tab's rows, in its words."""
    ladder = bot.ladder
    if ladder is None:
        return ()
    if isinstance(ladder, LadderUnavailable):
        return (_ladder_field("Ladder", ladder.reason),)
    position = position_texts(ladder.position, plain_price)
    rows = (
        _ladder_field("Ladder", summary_line(ladder.summary, plain_money)),
        _ladder_field(
            "Average per cycle (net of fees)",
            recorded_average_text(ladder.recorded, plain_money),
        ),
        _ladder_field("Last price heard", position.last_price),
        _ladder_field("Lower edge", position.lower_edge),
        _ladder_field("Upper edge", position.upper_edge),
        _ladder_field("Stop loss", position.stop_loss),
        _ladder_field("Take profit", position.take_profit),
    )
    if position.liquidation is None:
        return rows
    return (*rows, _ladder_field("Liquidation price", position.liquidation))


#: The ladder's rows carry the Bots tab's own labels, which are longer than the other rows'.
_LADDER_LABEL_WIDTH = 32


def _ladder_field(label: str, value: str) -> ReportRow:
    return ReportRow((ReportCell(label, _LADDER_LABEL_WIDTH), ReportCell(value)))


_GRID_HEADS = (
    "BUY",
    "SELL",
    "STEP",
    "NET STEP",
    "PER CYCLE BEFORE FEES",
    "PER CYCLE AFTER FEES",
    "NOW",
)
_GRID_WIDTHS = (14, 14, 8, 10, 23, 22, 0)
GRIDS_LEGEND = (
    "Step and net step are designed (the saved parameters, read now); per cycle is an estimate "
    "(capital over the levels that hold an order); now is recorded (the saved run)."
)


def _grids_section(bot: BotStatusEntry) -> ReportSection:
    """`bot show --grids`: one row per grid, buy level and the sell level above it."""
    ladder = bot.ladder
    title = f"Grids of bot {bot.bot_id}"
    if not isinstance(ladder, GridLadder):
        reason = "No ladder." if ladder is None else ladder.reason
        return ReportSection(title, (ReportRow.of(reason),))
    notes = [GRIDS_LEGEND]
    notes.append(net_figures_note(ladder.summary))
    if ladder.run_note:
        notes.append(ladder.run_note)
    return ReportSection(
        title,
        (
            _grid_row(_GRID_HEADS),
            *(_grid_row(_grid_cells(row)) for row in ladder.rows),
            *(ReportRow.of(note) for note in notes),
        ),
        has_header=True,
    )


def _grid_row(cells: tuple[str, ...]) -> ReportRow:
    return ReportRow(
        tuple(
            ReportCell(text, width)
            for text, width in zip(cells, _GRID_WIDTHS, strict=True)
        )
    )


def _quote_cell(value: Decimal | None) -> str:
    return NO_VALUE if value is None else small_money_text(value, plain_money)


def _grid_cells(row: LadderRow) -> tuple[str, ...]:
    return (
        plain_price(row.buy),
        plain_price(row.sell),
        percent_of(row.step_fraction),
        NO_VALUE if row.net_fraction is None else percent_of(row.net_fraction),
        _quote_cell(row.gross_quote),
        _quote_cell(row.net_quote),
        row.state.value,
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

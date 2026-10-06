from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import Readout
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    ratio_key,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

_LOSING_PROFIT_FACTOR_BADGE = "Risk"
#: A figure with no verdict attached — a raw number in the extended dump,
#: or a drawdown of exactly zero. `Tone.NEUTRAL` leaves the platform's
#: text colour, which is what the old empty-string sentinel meant before a
#: tone could express "no verdict" directly.
_NEUTRAL = Tone.NEUTRAL
_WIN_RATE_SUCCESS_THRESHOLD = 50.0

#: BOT-079 — `build_result_warning_text()`'s own dedicated line under the
#: stat cards (BOT-079 follow-up fix — an earlier version of this squeezed
#: these into the Net PnL badge, a small fixed-size pill; a 2-warning
#: combined string overflowed it and forced font-shrinking/eliding hacks in
#: `MetricCard.qml` to compensate. A full-width line has room for a real
#: sentence and doesn't fight the badge's layout). Informational only — task
#: explicitly warns against "nhuộm đỏ toàn màn hình như thể sai", so this is
#: one quiet line, not a colored-in card.
_FEE_WARNING_NOTE = '⚠ Fees account for a large share of the result — see "Total Fees Paid" in the extended metrics.'
_FREQUENCY_WARNING_NOTE = "⚠ High trade frequency — averaging only {bars} bars/trade."
#: BOT-080 — same dedicated-line mechanism as the 2 notes above, extended to
#: the in-sample/out-of-sample check. Interpolates the 2 raw numbers
#: directly into the sentence (not just "diverges") so the warning is
#: self-explanatory without a popup click, per the user's explicit decision
#: to reuse BOT-079's resultWarningText for this rather than a separate UI.
#: EPIC-027B/027D — a Spot run drops what a Spot market cannot execute.
_IGNORED_SHORTS_NOTE = "{count} short/cover signal(s) ignored (Spot is long-only)."
#: EPIC-027C — entries an exchange filter refused; they opened nothing.
_REJECTED_ENTRIES_NOTE = (
    "{count} entr(y/ies) rejected by exchange filters (below the minimum "
    "quantity or notional)."
)
_OUT_OF_SAMPLE_DIVERGENCE_NOTE = (
    "⚠ Possible overfitting — In-sample {in_sample} but Out-of-sample {out_of_sample}."
)


@dataclass(frozen=True)
class StatCardData:
    """@brief One figure of the report, as a raw value and the kind it is —
    `AppValueFormatter` writes the text (`EPIC-033N`).

    @details Carries a `Tone`, not a colour. This used to hold
    `BULL_COLOR`/`BEAR_COLOR` hex strings computed just above, which is the
    "literal with extra steps" pattern the engine's `Tone` docstring names
    explicitly: the domain comparison (`net_profit >= 0`) belongs up here,
    where the domain knowledge is, but only its *answer* should cross into
    a widget. What green means is the theme's business, not this module's.

    It carries the figure, not its text, for the same reason: a screen that
    receives "1,234.00" cannot sort, compare or re-round it, and a second
    screen formatting the same number writes it differently. `key` is the
    figure's row in a read-out and the formatter's context (`ratio_key` marks
    a ratio); `badge_figure` is a second figure or a few words beside it, on a
    row of its own named `badge_title`.
    """

    key: str
    title: str
    figure: DisplayValue
    kind: ColumnKind
    value_tone: Tone
    suffix: str = ""
    badge_title: str = ""
    badge_figure: DisplayValue = None
    badge_kind: ColumnKind = ColumnKind.TEXT
    badge_tone: Tone = Tone.NEUTRAL

    @property
    def value(self) -> str:
        """The figure as the formatter writes it."""
        return write_value(self.kind, self.figure, self.key)

    @property
    def badge_text(self) -> str:
        """The badge as the formatter writes it; empty when there is none."""
        return write_value(self.badge_kind, self.badge_figure, f"{self.key}.badge")


def compute_max_drawdown_amount(equity_curve: list[tuple[datetime, float]]) -> float:
    """
    @brief The dollar amount at the SAME trough that produced
    `BacktestMetrics.max_drawdown_percent`.
    @details Deliberately re-implements `BacktestMetrics`'s private
    `_max_drawdown_percent` peak-tracking loop exactly (same tie-breaking:
    only a strictly larger percent replaces the running max) rather than
    adding a field to `BacktestMetrics` — BOT-055 §2 explicit constraint.
    Two independent calls over the same `equity_curve` must agree on WHICH
    bar is the trough, or the $ figure and the % badge would describe two
    different moments.
    """
    peak: float | None = None
    max_drawdown_percent = 0.0
    max_drawdown_amount = 0.0
    for _, equity in equity_curve:
        if peak is None or equity > peak:
            peak = equity
        if peak:
            drawdown_amount = peak - equity
            drawdown_percent = drawdown_amount / peak * 100
            if drawdown_percent > max_drawdown_percent:
                max_drawdown_percent = drawdown_percent
                max_drawdown_amount = drawdown_amount
    return max_drawdown_amount


def build_result_warning_text(result: BacktestResult) -> str:
    """@brief BOT-079: 1 sentence (2 joined with a middle dot when both fire)
    for a dedicated line under the stat cards — empty string when neither
    flag is up, which QML reads as "hide this row entirely". Kept separate
    from `build_primary_stat_cards()`/`build_extended_stat_cards()` on
    purpose: those feed fixed-size `MetricCard` pills with no room for a
    sentence, this feeds a full-width `Text` that can wrap."""
    metrics = result.metrics
    notes = []
    if metrics.has_high_fee_ratio:
        notes.append(_FEE_WARNING_NOTE)
    if metrics.has_high_trade_frequency:
        notes.append(
            _FREQUENCY_WARNING_NOTE.format(
                bars=write_value(
                    ColumnKind.QUANTITY,
                    metrics.avg_bars_per_trade,
                    ratio_key("bars_per_trade"),
                )
            )
        )
    out_of_sample = result.out_of_sample
    if out_of_sample is not None and out_of_sample.has_high_divergence:
        notes.append(
            _OUT_OF_SAMPLE_DIVERGENCE_NOTE.format(
                in_sample=write_value(
                    ColumnKind.PERCENT,
                    out_of_sample.in_sample.metrics.net_profit_percent,
                ),
                out_of_sample=write_value(
                    ColumnKind.PERCENT,
                    out_of_sample.out_of_sample.metrics.net_profit_percent,
                ),
            )
        )
    if result.ignored_short_signals:
        notes.append(
            _IGNORED_SHORTS_NOTE.format(
                count=write_value(ColumnKind.QUANTITY, result.ignored_short_signals)
            )
        )
    if result.rejected_entries:
        notes.append(
            _REJECTED_ENTRIES_NOTE.format(
                count=write_value(ColumnKind.QUANTITY, result.rejected_entries)
            )
        )
    return "   •   ".join(notes)


def build_primary_stat_cards(result: BacktestResult) -> list[StatCardData]:
    """The 4 always-visible cards (BOT-055 §2)."""
    metrics = result.metrics
    winners = sum(1 for trade in result.trades if trade.pnl > 0)
    total = len(result.trades)
    drawdown_amount = compute_max_drawdown_amount(result.equity_curve)

    profit_tone = Tone.POSITIVE if metrics.net_profit >= 0 else Tone.NEGATIVE
    win_rate_tone = (
        Tone.POSITIVE
        if metrics.percent_profitable >= _WIN_RATE_SUCCESS_THRESHOLD
        else Tone.NEGATIVE
    )
    profit_factor_tone = Tone.POSITIVE if metrics.profit_factor >= 1 else Tone.NEGATIVE

    return [
        StatCardData(
            key="net_pnl",
            title="Net PnL",
            figure=metrics.net_profit,
            kind=ColumnKind.MONEY,
            value_tone=profit_tone,
            suffix="USD",
            badge_title="Net PnL (%)",
            badge_figure=metrics.net_profit_percent,
            badge_kind=ColumnKind.PERCENT,
            badge_tone=profit_tone,
        ),
        StatCardData(
            key="max_drawdown",
            title="Max Drawdown",
            figure=drawdown_amount,
            kind=ColumnKind.MONEY,
            value_tone=Tone.NEGATIVE if drawdown_amount > 0 else _NEUTRAL,
            suffix="USD",
            badge_title="Max Drawdown (%)",
            # A loss is marked by its minus; `or 0.0` keeps a drawdown of
            # exactly zero from reading "-0.00%".
            badge_figure=-metrics.max_drawdown_percent or 0.0,
            badge_kind=ColumnKind.PERCENT,
            badge_tone=Tone.NEGATIVE,
        ),
        StatCardData(
            key="win_rate",
            title="Win Rate",
            figure=metrics.percent_profitable,
            kind=ColumnKind.PERCENT,
            value_tone=win_rate_tone,
            badge_title="Winning / closed trades",
            badge_figure=(
                f"{write_value(ColumnKind.QUANTITY, winners)}"
                f" / {write_value(ColumnKind.QUANTITY, total)}"
            ),
            badge_tone=_NEUTRAL,
        ),
        StatCardData(
            key=ratio_key("profit_factor"),
            title="Profit Factor",
            figure=metrics.profit_factor,
            kind=ColumnKind.QUANTITY,
            value_tone=profit_factor_tone,
            badge_title="Profit Factor verdict",
            badge_figure=(
                _LOSING_PROFIT_FACTOR_BADGE if metrics.profit_factor < 1 else None
            ),
            badge_tone=Tone.NEGATIVE,
        ),
    ]


def stat_cards_to_qml(cards: list[StatCardData]) -> list[dict[str, object]]:
    """Converts to the plain-dict shape the view model carries.

    camelCase keys are a leftover from when a QML `Repeater` read these
    directly; the QtWidgets panels now read the same keys, so renaming them
    is a separate change with no benefit here. A figure travels raw, with its
    kind (`cards_readout` writes it); the dict never holds a figure's text."""
    return [
        {
            "key": card.key,
            "title": card.title,
            "figure": card.figure,
            "kind": card.kind,
            "valueTone": card.value_tone,
            "suffix": card.suffix,
            "badgeTitle": card.badge_title,
            "badgeFigure": card.badge_figure,
            "badgeKind": card.badge_kind,
            "badgeTone": card.badge_tone,
        }
        for card in cards
    ]


_BADGE_SUFFIX = ".badge"


def badge_key(card_key: str) -> str:
    """The read-out row of a card's badge."""
    return f"{card_key}{_BADGE_SUFFIX}"


def _row_title(title: object, suffix: object) -> str:
    return f"{title} ({suffix})" if suffix else str(title)


def cards_readout(cards: Sequence[Mapping[str, object]]) -> Readout:
    """The report's figures as one read-out: a row per card, and a row under
    it for its badge when it has one. The unit sits in the title, the value is
    raw, and `AppValueFormatter` writes it (`EPIC-033N`)."""
    specs: list[ColumnSpec] = []
    values: dict[str, DisplayValue] = {}
    for card in cards:
        key = str(card["key"])
        title = _row_title(card["title"], card.get("suffix", ""))
        # The dict is `stat_cards_to_qml`'s: its figure is a `DisplayValue`
        # and its kind a `ColumnKind`, which a `Mapping[str, object]` cannot say.
        specs.append(ColumnSpec(key, title, cast(ColumnKind, card["kind"])))
        values[key] = cast(DisplayValue, card["figure"])
        badge_figure = cast(DisplayValue, card.get("badgeFigure"))
        if badge_figure is None:
            continue
        badge_kind = cast(ColumnKind, card.get("badgeKind", ColumnKind.TEXT))
        specs.append(
            ColumnSpec(badge_key(key), str(card.get("badgeTitle", "")), badge_kind)
        )
        values[badge_key(key)] = badge_figure
    return Readout(tuple(specs), values)


def build_extended_stat_cards(result: BacktestResult) -> list[StatCardData]:
    """Revealed by "Mở rộng chỉ số chi tiết" — every remaining
    `BacktestMetrics` field BOT-055 §2 lists, all neutral-colored (no
    sign/badge — this row is a raw data dump, not a verdict)."""
    metrics = result.metrics

    def money(key: str, title: str, figure: float) -> StatCardData:
        return StatCardData(key, title, figure, ColumnKind.MONEY, _NEUTRAL, "USD")

    def count(key: str, title: str, figure: int, suffix: str = "") -> StatCardData:
        return StatCardData(key, title, figure, ColumnKind.QUANTITY, _NEUTRAL, suffix)

    def ratio(name: str, title: str, figure: float) -> StatCardData:
        return StatCardData(
            ratio_key(name), title, figure, ColumnKind.QUANTITY, _NEUTRAL
        )

    return [
        money("gross_profit", "Gross Profit", metrics.gross_profit),
        money("gross_loss", "Gross Loss", metrics.gross_loss),
        money("avg_trade", "Avg Trade", metrics.avg_trade),
        money("avg_winning_trade", "Avg Winning Trade", metrics.avg_winning_trade),
        money("avg_losing_trade", "Avg Losing Trade", metrics.avg_losing_trade),
        money(
            "largest_winning_trade",
            "Largest Winning Trade",
            metrics.largest_winning_trade,
        ),
        money(
            "largest_losing_trade",
            "Largest Losing Trade",
            metrics.largest_losing_trade,
        ),
        count(
            "total_closed_trades", "Total Closed Trades", metrics.total_closed_trades
        ),
        ratio("sharpe", "Sharpe Ratio", metrics.sharpe_ratio),
        ratio("sortino", "Sortino Ratio", metrics.sortino_ratio),
        ratio("calmar", "Calmar Ratio", metrics.calmar_ratio),
        count(
            "max_drawdown_duration",
            "Max Drawdown Duration",
            metrics.max_drawdown_duration_bars,
            "bars",
        ),
        count(
            "max_consecutive_wins",
            "Max Consecutive Wins",
            metrics.max_consecutive_wins,
        ),
        count(
            "max_consecutive_losses",
            "Max Consecutive Losses",
            metrics.max_consecutive_losses,
        ),
        StatCardData(
            "total_fees_paid",
            "Total Fees Paid",
            metrics.total_fees_paid,
            ColumnKind.MONEY,
            # BOT-079: the one card in this "raw data dump" row that DOES
            # get a color — fee dominance is exactly the fact this field
            # exists to surface, so when it's true, don't render it neutral.
            Tone.NEGATIVE if metrics.has_high_fee_ratio else _NEUTRAL,
            "USD",
        ),
    ]

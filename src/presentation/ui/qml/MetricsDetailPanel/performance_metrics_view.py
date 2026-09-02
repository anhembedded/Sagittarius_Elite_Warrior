from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone

_INFINITY_DISPLAY = "∞"  # "∞" — profit_factor is float("inf") with 0 losers
_LOSING_PROFIT_FACTOR_BADGE = "Rủi ro"
#: A figure with no verdict attached — a raw number in the extended dump,
#: or a drawdown of exactly zero. `Tone.NEUTRAL` resolves to `textPrimary`,
#: which is what the old empty-string sentinel meant before the widget layer
#: could express "no verdict" directly.
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
_FEE_WARNING_NOTE = (
    '⚠ Phí giao dịch chiếm phần lớn kết quả — xem "Total Fees Paid" ở chỉ số mở rộng.'
)
_FREQUENCY_WARNING_NOTE = (
    "⚠ Tần suất giao dịch cao — trung bình chỉ {bars:.1f} bar/lệnh."
)
#: BOT-080 — same dedicated-line mechanism as the 2 notes above, extended to
#: the in-sample/out-of-sample check. Interpolates the 2 raw numbers
#: directly into the sentence (not just "diverges") so the warning is
#: self-explanatory without a popup click, per the user's explicit decision
#: to reuse BOT-079's resultWarningText for this rather than a separate UI.
_OUT_OF_SAMPLE_DIVERGENCE_NOTE = (
    "⚠ Có thể đang overfit — In-sample {in_sample:+.2f}% nhưng "
    "Out-of-sample {out_of_sample:+.2f}%."
)


@dataclass(frozen=True)
class StatCardData:
    """@brief Everything one stat card needs, computed here so the widget
    stays a dumb renderer — this repo's existing Presenter/ViewModel split.

    @details Carries a `Tone`, not a colour. This used to hold
    `BULL_COLOR`/`BEAR_COLOR` hex strings computed just above, which is the
    "literal with extra steps" pattern the engine's `Tone` docstring names
    explicitly: the domain comparison (`net_profit >= 0`) belongs up here,
    where the domain knowledge is, but only its *answer* should cross into
    a widget. What green means is the theme's business, not this module's.
    """

    title: str
    value: str
    value_tone: Tone
    suffix: str
    badge_text: str
    badge_tone: Tone


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


def _signed(value: float, decimals: int = 2) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:,.{decimals}f}"


def _profit_factor_text(profit_factor: float) -> str:
    if profit_factor == float("inf"):
        return _INFINITY_DISPLAY
    return f"{profit_factor:.3f}"


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
        notes.append(_FREQUENCY_WARNING_NOTE.format(bars=metrics.avg_bars_per_trade))
    out_of_sample = result.out_of_sample
    if out_of_sample is not None and out_of_sample.has_high_divergence:
        notes.append(
            _OUT_OF_SAMPLE_DIVERGENCE_NOTE.format(
                in_sample=out_of_sample.in_sample.metrics.net_profit_percent,
                out_of_sample=out_of_sample.out_of_sample.metrics.net_profit_percent,
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
            title="Tổng Lãi/Lỗ (Net PnL)",
            value=_signed(metrics.net_profit),
            value_tone=profit_tone,
            suffix="USD",
            badge_text=f"{_signed(metrics.net_profit_percent)}%",
            badge_tone=profit_tone,
        ),
        StatCardData(
            title="Mức sụt giảm tối đa (Max Drawdown)",
            value=f"{drawdown_amount:,.2f}",
            value_tone=Tone.NEGATIVE if drawdown_amount > 0 else _NEUTRAL,
            suffix="USD",
            badge_text=f"-{metrics.max_drawdown_percent:.2f}%",
            badge_tone=Tone.NEGATIVE,
        ),
        StatCardData(
            title="Tỷ lệ thắng (Win Rate)",
            value=f"{metrics.percent_profitable:.2f}%",
            value_tone=win_rate_tone,
            suffix="",
            badge_text=f"({winners}/{total} lệnh)",
            badge_tone=_NEUTRAL,
        ),
        StatCardData(
            title="Hệ số lãi (Profit Factor)",
            value=_profit_factor_text(metrics.profit_factor),
            value_tone=profit_factor_tone,
            suffix="",
            badge_text=_LOSING_PROFIT_FACTOR_BADGE if metrics.profit_factor < 1 else "",
            badge_tone=Tone.NEGATIVE,
        ),
    ]


def stat_cards_to_qml(cards: list[StatCardData]) -> list[dict[str, str | Tone]]:
    """Converts to the plain-dict shape the view model carries.

    camelCase keys are a leftover from when a QML `Repeater` read these
    directly; the QtWidgets panels now read the same keys, so renaming them
    is a separate change with no benefit here."""
    return [
        {
            "title": card.title,
            "value": card.value,
            "valueTone": card.value_tone,
            "suffix": card.suffix,
            "badgeText": card.badge_text,
            "badgeTone": card.badge_tone,
        }
        for card in cards
    ]


def build_extended_stat_cards(result: BacktestResult) -> list[StatCardData]:
    """Revealed by "Mở rộng chỉ số chi tiết" — every remaining
    `BacktestMetrics` field BOT-055 §2 lists, all neutral-colored (no
    sign/badge — this row is a raw data dump, not a verdict)."""
    metrics = result.metrics
    cards = [
        StatCardData(
            "Gross Profit",
            f"{metrics.gross_profit:,.2f}",
            _NEUTRAL,
            "USD",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Gross Loss",
            f"{metrics.gross_loss:,.2f}",
            _NEUTRAL,
            "USD",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Avg Trade",
            f"{metrics.avg_trade:,.2f}",
            _NEUTRAL,
            "USD",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Avg Winning Trade",
            f"{metrics.avg_winning_trade:,.2f}",
            _NEUTRAL,
            "USD",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Avg Losing Trade",
            f"{metrics.avg_losing_trade:,.2f}",
            _NEUTRAL,
            "USD",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Largest Winning Trade",
            f"{metrics.largest_winning_trade:,.2f}",
            _NEUTRAL,
            "USD",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Largest Losing Trade",
            f"{metrics.largest_losing_trade:,.2f}",
            _NEUTRAL,
            "USD",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Total Closed Trades",
            str(metrics.total_closed_trades),
            _NEUTRAL,
            "",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Sharpe Ratio",
            f"{metrics.sharpe_ratio:.2f}",
            _NEUTRAL,
            "",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Sortino Ratio",
            f"{metrics.sortino_ratio:.2f}",
            _NEUTRAL,
            "",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Calmar Ratio",
            f"{metrics.calmar_ratio:.2f}",
            _NEUTRAL,
            "",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Max Drawdown Duration",
            str(metrics.max_drawdown_duration_bars),
            _NEUTRAL,
            "bars",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Max Consecutive Wins",
            str(metrics.max_consecutive_wins),
            _NEUTRAL,
            "",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Max Consecutive Losses",
            str(metrics.max_consecutive_losses),
            _NEUTRAL,
            "",
            "",
            _NEUTRAL,
        ),
        StatCardData(
            "Total Fees Paid",
            f"{metrics.total_fees_paid:,.2f}",
            # BOT-079: the one card in this "raw data dump" row that DOES
            # get a color — fee dominance is exactly the fact this field
            # exists to surface, so when it's true, don't render it neutral.
            Tone.NEGATIVE if metrics.has_high_fee_ratio else _NEUTRAL,
            "USD",
            "",
            _NEUTRAL,
        ),
    ]

    # BOT-080 — only present when the range was long enough to split
    # (BacktestResult.out_of_sample is None otherwise). Raw numbers live
    # here (same precedent as "Total Fees Paid" backing the fee warning);
    # the "is this concerning" signal is build_result_warning_text()'s job.
    out_of_sample = result.out_of_sample
    if out_of_sample is not None:
        divergence_tone = (
            Tone.NEGATIVE if out_of_sample.has_high_divergence else _NEUTRAL
        )
        cards.append(
            StatCardData(
                "In-Sample Net Profit",
                f"{out_of_sample.in_sample.metrics.net_profit_percent:+.2f}",
                _NEUTRAL,
                "%",
                "",
                _NEUTRAL,
            )
        )
        cards.append(
            StatCardData(
                "Out-of-Sample Net Profit",
                f"{out_of_sample.out_of_sample.metrics.net_profit_percent:+.2f}",
                divergence_tone,
                "%",
                "",
                _NEUTRAL,
            )
        )

    return cards

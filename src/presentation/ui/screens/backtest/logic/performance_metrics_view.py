from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)

_INFINITY_DISPLAY = "∞"  # "∞" — profit_factor is float("inf") with 0 losers
_LOSING_PROFIT_FACTOR_BADGE = "Rủi ro"
_NEUTRAL_COLOR = ""  # empty = "let QML fall back to Theme.muted/textPrimary"


@dataclass(frozen=True)
class StatCardData:
    """@brief Everything one `MetricCard.qml` instance needs — computed here
    so the QML stays a dumb renderer, matching this repo's existing
    Presenter/ViewModel split."""

    title: str
    value: str
    value_color: str
    suffix: str
    badge_text: str
    badge_color: str


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


def build_primary_stat_cards(result: BacktestResult) -> list[StatCardData]:
    """The 4 always-visible cards (BOT-055 §2)."""
    metrics = result.metrics
    winners = sum(1 for trade in result.trades if trade.pnl > 0)
    total = len(result.trades)
    drawdown_amount = compute_max_drawdown_amount(result.equity_curve)

    profit_color = BULL_COLOR if metrics.net_profit >= 0 else BEAR_COLOR
    win_rate_color = BULL_COLOR if metrics.percent_profitable >= 50 else BEAR_COLOR
    profit_factor_color = BULL_COLOR if metrics.profit_factor >= 1 else BEAR_COLOR

    return [
        StatCardData(
            title="Tổng Lãi/Lỗ (Net PnL)",
            value=_signed(metrics.net_profit),
            value_color=profit_color,
            suffix="USD",
            badge_text=f"{_signed(metrics.net_profit_percent)}%",
            badge_color=profit_color,
        ),
        StatCardData(
            title="Mức sụt giảm tối đa (Max Drawdown)",
            value=f"{drawdown_amount:,.2f}",
            value_color=BEAR_COLOR if drawdown_amount > 0 else _NEUTRAL_COLOR,
            suffix="USD",
            badge_text=f"-{metrics.max_drawdown_percent:.2f}%",
            badge_color=BEAR_COLOR,
        ),
        StatCardData(
            title="Tỷ lệ thắng (Win Rate)",
            value=f"{metrics.percent_profitable:.2f}%",
            value_color=win_rate_color,
            suffix="",
            badge_text=f"({winners}/{total} lệnh)",
            badge_color=_NEUTRAL_COLOR,
        ),
        StatCardData(
            title="Hệ số lãi (Profit Factor)",
            value=_profit_factor_text(metrics.profit_factor),
            value_color=profit_factor_color,
            suffix="",
            badge_text=_LOSING_PROFIT_FACTOR_BADGE if metrics.profit_factor < 1 else "",
            badge_color=BEAR_COLOR,
        ),
    ]


def stat_cards_to_qml(cards: list[StatCardData]) -> list[dict[str, str]]:
    """Converts to the plain-dict shape `MetricCard.qml`'s `Repeater` model
    expects (camelCase keys — QML property names, not Python field names)."""
    return [
        {
            "title": card.title,
            "value": card.value,
            "valueColor": card.value_color,
            "suffix": card.suffix,
            "badgeText": card.badge_text,
            "badgeColor": card.badge_color,
        }
        for card in cards
    ]


def build_extended_stat_cards(result: BacktestResult) -> list[StatCardData]:
    """Revealed by "Mở rộng chỉ số chi tiết" — every remaining
    `BacktestMetrics` field BOT-055 §2 lists, all neutral-colored (no
    sign/badge — this row is a raw data dump, not a verdict)."""
    metrics = result.metrics
    return [
        StatCardData(
            "Gross Profit",
            f"{metrics.gross_profit:,.2f}",
            _NEUTRAL_COLOR,
            "USD",
            "",
            _NEUTRAL_COLOR,
        ),
        StatCardData(
            "Gross Loss",
            f"{metrics.gross_loss:,.2f}",
            _NEUTRAL_COLOR,
            "USD",
            "",
            _NEUTRAL_COLOR,
        ),
        StatCardData(
            "Avg Trade",
            f"{metrics.avg_trade:,.2f}",
            _NEUTRAL_COLOR,
            "USD",
            "",
            _NEUTRAL_COLOR,
        ),
        StatCardData(
            "Avg Winning Trade",
            f"{metrics.avg_winning_trade:,.2f}",
            _NEUTRAL_COLOR,
            "USD",
            "",
            _NEUTRAL_COLOR,
        ),
        StatCardData(
            "Avg Losing Trade",
            f"{metrics.avg_losing_trade:,.2f}",
            _NEUTRAL_COLOR,
            "USD",
            "",
            _NEUTRAL_COLOR,
        ),
        StatCardData(
            "Largest Winning Trade",
            f"{metrics.largest_winning_trade:,.2f}",
            _NEUTRAL_COLOR,
            "USD",
            "",
            _NEUTRAL_COLOR,
        ),
        StatCardData(
            "Largest Losing Trade",
            f"{metrics.largest_losing_trade:,.2f}",
            _NEUTRAL_COLOR,
            "USD",
            "",
            _NEUTRAL_COLOR,
        ),
        StatCardData(
            "Total Closed Trades",
            str(metrics.total_closed_trades),
            _NEUTRAL_COLOR,
            "",
            "",
            _NEUTRAL_COLOR,
        ),
    ]

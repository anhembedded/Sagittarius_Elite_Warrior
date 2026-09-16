"""State behind `MetricsDetailPanel.qml` — "CHỈ SỐ CHI TIẾT BACKTEST".

@par What this replaced, and what is no longer true above
It was written standalone (user decision 2026-08-30) beside the shipped
`ExtendedMetricsDialog`/`StatGrid`, so that enhancing the live dialog in place
could not break it. It is the live one now: `BackTestModalsHost` builds it, and
`EPIC-025` PR 4.3i deleted `qml/StatGrid/` once nothing constructed it any
more. This docstring said "standalone and not wired to a screen" for two
epics after that stopped being so, which is why PR 4.3h re-measures rather than
reading a package's own notes.

It reuses the real, tested pure functions (`StatCardData`,
`build_extended_stat_cards`) rather than re-deriving a card's value or colour,
and adds only what those do not compute: section grouping, verdict badges on
the risk-ratio cards, and the gross-profit-vs-loss bar. See NOTES.md for
exactly which numbers are real and which are an invented heuristic.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone

from .performance_metrics_view import StatCardData

#: Which of the mockup's 4 sections each existing extended-stat card title
#: belongs to. A card whose title is not listed here (Total Fees Paid,
#: In-Sample/Out-of-Sample Net Profit — the mockup simply doesn't show
#: those) falls into `_OTHER_GROUP` instead of silently disappearing.
_GROUP_ORDER: tuple[str, ...] = (
    "PROFIT & LOSS",
    "AVERAGE PER TRADE",
    "RISK",
    "STREAKS",
    "OTHER",
)
_OTHER_GROUP = "OTHER"
_GROUP_BY_TITLE: dict[str, str] = {
    "Gross Profit": "PROFIT & LOSS",
    "Gross Loss": "PROFIT & LOSS",
    "Avg Trade": "PROFIT & LOSS",
    "Total Closed Trades": "PROFIT & LOSS",
    "Avg Winning Trade": "AVERAGE PER TRADE",
    "Avg Losing Trade": "AVERAGE PER TRADE",
    "Largest Winning Trade": "AVERAGE PER TRADE",
    "Largest Losing Trade": "AVERAGE PER TRADE",
    "Sharpe Ratio": "RISK",
    "Sortino Ratio": "RISK",
    "Calmar Ratio": "RISK",
    "Max Drawdown Duration": "RISK",
    "Max Consecutive Wins": "STREAKS",
    "Max Consecutive Losses": "STREAKS",
}

#: Consecutive-loss count at which the mockup's "Cảnh báo" badge appears.
#: Arbitrary — no existing rule in this codebase names a threshold, so this
#: is this widget's own invented heuristic (NOTES.md).
_CONSECUTIVE_LOSSES_WARNING_THRESHOLD = 10
_SECONDS_PER_DAY = 86_400

#: `_ratio_verdict`'s (Sharpe/Sortino) bucket edges — see its docstring.
_RATIO_GOOD_THRESHOLD = 1.0
_RATIO_EXCELLENT_THRESHOLD = 2.0

#: `_calmar_verdict`'s bucket edges — see its docstring.
_CALMAR_WEAK_THRESHOLD = 0.5
_CALMAR_ACCEPTABLE_THRESHOLD = 1.0


def _ratio_verdict(value: float) -> tuple[str, Tone]:
    """Common Sharpe/Sortino heuristic: <0 poor, 0–1 mediocre, 1–2 good,
    >2 excellent. Not a spec anywhere in this codebase — see NOTES.md."""
    if value < 0:
        return "Very Poor", Tone.NEGATIVE
    if value < _RATIO_GOOD_THRESHOLD:
        return "Average", Tone.NEUTRAL
    if value < _RATIO_EXCELLENT_THRESHOLD:
        return "Good", Tone.POSITIVE
    return "Excellent", Tone.POSITIVE


def _calmar_verdict(value: float) -> tuple[str, Tone]:
    """Calmar = return / max drawdown. <0 means a net loss ("Âm"); the rest
    is the same invented-heuristic caveat as `_ratio_verdict` (NOTES.md)."""
    if value < 0:
        return "Negative", Tone.NEGATIVE
    if value < _CALMAR_WEAK_THRESHOLD:
        return "Weak", Tone.NEUTRAL
    if value < _CALMAR_ACCEPTABLE_THRESHOLD:
        return "Fair", Tone.NEUTRAL
    return "Strong", Tone.POSITIVE


def _consecutive_losses_verdict(count: int) -> tuple[str, Tone]:
    if count >= _CONSECUTIVE_LOSSES_WARNING_THRESHOLD:
        return "Warning", Tone.NEGATIVE
    return "", Tone.NEUTRAL


#: Card title -> function computing (badge_text, badge_tone) from the
#: card's own numeric value. Applied only to cards already in `_GROUP_BY_TITLE`
#: that the mockup shows with a verdict badge; every other card keeps
#: whatever `build_extended_stat_cards()` already gave it (usually none).
_VERDICT_BY_TITLE: dict[str, Callable[[float], tuple[str, Tone]]] = {
    "Sharpe Ratio": _ratio_verdict,
    "Sortino Ratio": _ratio_verdict,
    "Calmar Ratio": _calmar_verdict,
    "Max Consecutive Losses": _consecutive_losses_verdict,
}


def _as_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


class MetricsDetailVM(QObject):
    """
    @brief The extended-metrics readout, grouped into sections, with
    invented verdict badges on the risk-ratio cards and a gross-profit-vs-
    loss bar — everything `StatGridVM` already computes, plus what the
    mockup adds on top of it.
    """

    stateChanged = Signal()
    copyRequested = Signal()
    closeRequested = Signal()

    def __init__(
        self,
        *,
        get_cards: Callable[[], Sequence[StatCardData]],
        get_gross_profit: Callable[[], float],
        get_gross_loss: Callable[[], float],
        get_profit_factor: Callable[[], float],
        get_total_closed_trades: Callable[[], int],
        get_fee_rate_percent: Callable[[], float],
        get_timeframe_seconds: Callable[[], int],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_cards = get_cards
        self._get_gross_profit = get_gross_profit
        self._get_gross_loss = get_gross_loss
        self._get_profit_factor = get_profit_factor
        self._get_total_closed_trades = get_total_closed_trades
        self._get_fee_rate_percent = get_fee_rate_percent
        self._get_timeframe_seconds = get_timeframe_seconds

        self._groups: list[dict[str, object]] = []
        self._gross_profit_text = ""
        self._gross_loss_text = ""
        self._gross_profit_share = 0.0
        self._bar_caption = ""
        self._footer_text = ""

    @Property("QVariantList", notify=stateChanged)
    def groups(self) -> list[dict[str, object]]:
        return self._groups

    @Property(str, notify=stateChanged)
    def grossProfitText(self) -> str:
        return self._gross_profit_text

    @Property(str, notify=stateChanged)
    def grossLossText(self) -> str:
        return self._gross_loss_text

    @Property(float, notify=stateChanged)
    def grossProfitShare(self) -> float:
        """Fraction (0–1) of the bar the profit side fills — the loss side
        is `1 - grossProfitShare`, drawn by the `.qml` bar itself."""
        return self._gross_profit_share

    @Property(str, notify=stateChanged)
    def barCaption(self) -> str:
        return self._bar_caption

    @Property(str, notify=stateChanged)
    def footerText(self) -> str:
        return self._footer_text

    def refresh(self) -> None:
        self._recompute_groups()
        self._recompute_bar()
        self._recompute_footer()
        self.stateChanged.emit()

    @Slot()
    def requestCopy(self) -> None:
        self.copyRequested.emit()

    @Slot()
    def requestClose(self) -> None:
        self.closeRequested.emit()

    def _recompute_groups(self) -> None:
        cards = list(self._get_cards())
        timeframe_seconds = max(int(self._get_timeframe_seconds()), 1)

        rows_by_group: dict[str, list[dict[str, object]]] = {
            name: [] for name in _GROUP_ORDER
        }
        for card in cards:
            group = _GROUP_BY_TITLE.get(card.title, _OTHER_GROUP)
            badge_text = card.badge_text
            badge_tone = card.badge_tone
            value_tone = card.value_tone
            verdict = _VERDICT_BY_TITLE.get(card.title)
            numeric = _as_float(card.value)
            if verdict is not None and numeric is not None:
                badge_text, badge_tone = verdict(numeric)
                # The value itself takes the same verdict tone, not just the
                # badge — the mockup colours "-63.24" red, not only its
                # "Rất kém" pill.
                value_tone = badge_tone
            info_badge = ""
            if card.title == "Max Drawdown Duration" and numeric is not None:
                days = numeric * timeframe_seconds / _SECONDS_PER_DAY
                info_badge = f"≈ {days:.0f} days"
            rows_by_group[group].append(
                {
                    "title": card.title.upper(),
                    "value": card.value,
                    "suffix": card.suffix,
                    "tone": value_tone.name,
                    "badgeText": badge_text,
                    "badgeTone": badge_tone.name,
                    "infoBadge": info_badge,
                }
            )

        self._groups = [
            {"label": name, "rows": rows_by_group[name]}
            for name in _GROUP_ORDER
            if rows_by_group[name]
        ]

    def _recompute_bar(self) -> None:
        # `BacktestMetrics.gross_loss` is stored `<= 0` (sum of losing
        # trades' pnl) — the same convention `profit_factor = gross_profit /
        # abs(gross_loss)` already uses. `abs()` here, not `max(x, 0.0)`,
        # which would have silently zeroed out a real negative value.
        gross_profit = abs(self._get_gross_profit())
        gross_loss = abs(self._get_gross_loss())
        profit_factor = self._get_profit_factor()
        total = gross_profit + gross_loss

        self._gross_profit_text = f"+{gross_profit:,.2f}"
        self._gross_loss_text = f"-{gross_loss:,.2f}"
        self._gross_profit_share = gross_profit / total if total > 0 else 0.5

        loss_per_profit_dollar = gross_loss / gross_profit if gross_profit > 0 else 0.0
        profit_factor_text = (
            "∞" if profit_factor == float("inf") else f"{profit_factor:.3f}"
        )
        self._bar_caption = (
            f"Every $1 of profit comes with ${loss_per_profit_dollar:,.2f} of loss"
            f" — profit factor {profit_factor_text}"
        )

    def _recompute_footer(self) -> None:
        total_closed = self._get_total_closed_trades()
        fee_rate = self._get_fee_rate_percent()
        self._footer_text = (
            f"Based on {total_closed:,} closed trades · fee {fee_rate:g}% per trade"
        )

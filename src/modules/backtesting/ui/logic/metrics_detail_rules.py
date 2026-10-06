"""What the extended-metrics readout says, with no widget in sight.

## Where this came from

`EPIC-015` Phase 3 put all of this inside `MetricsDetailVM`, a `QObject`
re-publishing every value to `MetricsDetailPanel.qml` as a bindable attribute.
`EPIC-025` PR 4.3j deletes that `.qml` (ADR D21) and keeps the part that was
never about QML: which section each metric belongs to, what verdict a ratio
earns, how the gross-profit-vs-loss bar divides, and the plain text a "Copy
all" produces.

Pure functions over plain values, for the reason `range_rules.py` gives for the
time-range picker: this is the half that can be wrong without anything
crashing — a verdict one bucket out looks exactly like a run that earned it —
so it is tested with no dialog, no screen and no backtest engine.

## What is a measurement and what is a heuristic

`StatCardData` values arrive already computed by `performance_metrics_view.py`
from the run's real `BacktestMetrics`. Everything **this** module adds on top
is presentation, and two pieces of it are **invented**: the Sharpe/Sortino and
Calmar verdict buckets, and the consecutive-loss warning threshold. No spec in
this repository names them; they are the common rules of thumb, kept from the
design `EPIC-015` worked to, and they are labelled as such here so nobody reads
"Excellent" as a number the engine produced.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    ratio_key,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    DisplayValue,
)

from .performance_metrics_view import StatCardData

#: Which section each extended-stat card title belongs to. A card whose title
#: is not listed — e.g. Total Fees Paid — falls into `OTHER` rather than
#: silently disappearing.
GROUP_ORDER: tuple[str, ...] = (
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

#: Consecutive-loss count at which a warning appears. Invented: no rule in this
#: repository names a threshold.
_CONSECUTIVE_LOSSES_WARNING_THRESHOLD = 10

#: `_ratio_verdict`'s bucket edges — see its docstring.
_RATIO_GOOD_THRESHOLD = 1.0
_RATIO_EXCELLENT_THRESHOLD = 2.0

#: `_calmar_verdict`'s bucket edges — see its docstring.
_CALMAR_WEAK_THRESHOLD = 0.5
_CALMAR_ACCEPTABLE_THRESHOLD = 1.0

_DRAWDOWN_DURATION_TITLE = "Max Drawdown Duration"


@dataclass(frozen=True)
class MetricRow:
    """One metric as the readout shows it: the figure, and the verdict — if
    any — this module decided to put beside it.

    The figure is raw with its kind (`EPIC-033N`); `value` is how
    `AppValueFormatter` writes it, for the readout's table and the copied text.
    """

    key: str
    title: str
    figure: DisplayValue
    kind: ColumnKind
    suffix: str
    tone: Tone
    badge_text: str
    badge_tone: Tone
    #: A derived aside rather than a verdict — today only the drawdown
    #: duration's "≈ h:mm:ss", which needs the run's timeframe to compute.
    info: str = ""

    @property
    def value(self) -> str:
        return write_value(self.kind, self.figure, self.key)


@dataclass(frozen=True)
class MetricGroup:
    """One titled section of the readout, and the rows under it."""

    label: str
    rows: tuple[MetricRow, ...]


@dataclass(frozen=True)
class GrossBar:
    """The profit-against-loss bar: two figures, the share the profit side
    fills, and the sentence under it."""

    profit_text: str
    loss_text: str
    profit_share: float
    caption: str


def _ratio_verdict(value: float) -> tuple[str, Tone]:
    """Common Sharpe/Sortino rule of thumb: <0 poor, 0–1 mediocre, 1–2 good,
    >2 excellent. **Invented** — no spec in this repository says so."""
    if value < 0:
        return "Very Poor", Tone.NEGATIVE
    if value < _RATIO_GOOD_THRESHOLD:
        return "Average", Tone.NEUTRAL
    if value < _RATIO_EXCELLENT_THRESHOLD:
        return "Good", Tone.POSITIVE
    return "Excellent", Tone.POSITIVE


def _calmar_verdict(value: float) -> tuple[str, Tone]:
    """Calmar = return / max drawdown. Below zero is a net loss; the rest is
    the same invented-heuristic caveat as `_ratio_verdict`."""
    if value < 0:
        return "Negative", Tone.NEGATIVE
    if value < _CALMAR_WEAK_THRESHOLD:
        return "Weak", Tone.NEUTRAL
    if value < _CALMAR_ACCEPTABLE_THRESHOLD:
        return "Fair", Tone.NEUTRAL
    return "Strong", Tone.POSITIVE


def _consecutive_losses_verdict(count: float) -> tuple[str, Tone]:
    if count >= _CONSECUTIVE_LOSSES_WARNING_THRESHOLD:
        return "Warning", Tone.NEGATIVE
    return "", Tone.NEUTRAL


#: Card title → the function deciding its verdict from its own numeric value.
#: Every other card keeps whatever `build_extended_stat_cards()` gave it.
_VERDICT_BY_TITLE: Mapping[str, Callable[[float], tuple[str, Tone]]] = {
    "Sharpe Ratio": _ratio_verdict,
    "Sortino Ratio": _ratio_verdict,
    "Calmar Ratio": _calmar_verdict,
    "Max Consecutive Losses": _consecutive_losses_verdict,
}


def _as_float(figure: DisplayValue) -> float | None:
    """The figure as a number, or `None` for a figure that is not one — and
    for NaN, which no verdict bucket orders."""
    if isinstance(figure, bool) or not isinstance(figure, int | float):
        return None
    return None if math.isnan(figure) else float(figure)


def build_groups(
    cards: Sequence[StatCardData], *, timeframe_seconds: int
) -> tuple[MetricGroup, ...]:
    """Every card, in sections, with the verdicts this module adds.

    An empty section is dropped rather than rendered with a heading and
    nothing under it.
    """
    seconds = max(int(timeframe_seconds), 1)
    rows_by_group: dict[str, list[MetricRow]] = {name: [] for name in GROUP_ORDER}

    for card in cards:
        group = _GROUP_BY_TITLE.get(card.title, _OTHER_GROUP)
        badge_text = card.badge_text
        badge_tone = card.badge_tone
        value_tone = card.value_tone
        numeric = _as_float(card.figure)
        verdict = _VERDICT_BY_TITLE.get(card.title)
        if verdict is not None and numeric is not None:
            badge_text, badge_tone = verdict(numeric)
            # The figure takes the verdict's tone too, not only its badge: a
            # Sharpe of -63.24 reads red, not neutral beside a red pill.
            value_tone = badge_tone
        info = ""
        if card.title == _DRAWDOWN_DURATION_TITLE and numeric is not None:
            # Bars are a count; the time they span is a duration.
            info = "≈ " + write_value(
                ColumnKind.DURATION, timedelta(seconds=numeric * seconds)
            )
        rows_by_group[group].append(
            MetricRow(
                key=card.key,
                title=card.title.upper(),
                figure=card.figure,
                kind=card.kind,
                suffix=card.suffix,
                tone=value_tone,
                badge_text=badge_text,
                badge_tone=badge_tone,
                info=info,
            )
        )

    return tuple(
        MetricGroup(label=name, rows=tuple(rows_by_group[name]))
        for name in GROUP_ORDER
        if rows_by_group[name]
    )


def build_gross_bar(
    *, gross_profit: float, gross_loss: float, profit_factor: float
) -> GrossBar:
    """The profit-against-loss bar.

    `BacktestMetrics.gross_loss` is stored `<= 0` (the sum of losing trades'
    pnl), the same convention `profit_factor = gross_profit / abs(gross_loss)`
    already uses — hence `abs()` rather than `max(x, 0.0)`, which would
    silently zero a real negative.
    """
    profit = abs(gross_profit)
    loss = abs(gross_loss)
    total = profit + loss
    loss_per_profit_dollar = loss / profit if profit > 0 else 0.0
    factor_text = write_value(
        ColumnKind.QUANTITY, profit_factor, ratio_key("profit_factor")
    )
    return GrossBar(
        profit_text=write_value(ColumnKind.MONEY, profit),
        # The loss carries its minus; `-0.0` (no loss) reads `0.00`.
        loss_text=write_value(ColumnKind.MONEY, -loss),
        # A run with neither profit nor loss splits the bar evenly rather than
        # reading as a total loss.
        profit_share=profit / total if total > 0 else 0.5,
        caption=(
            "Every $1 of profit comes with "
            f"${write_value(ColumnKind.MONEY, loss_per_profit_dollar)} of loss"
            f" — profit factor {factor_text}"
        ),
    )


def build_footer(*, total_closed_trades: int, fee_rate_percent: float) -> str:
    """The line that says what the numbers above were computed from."""
    return (
        f"Based on {write_value(ColumnKind.QUANTITY, total_closed_trades)}"
        f" closed trades · fee {write_value(ColumnKind.PERCENT, fee_rate_percent)}"
        " per trade"
    )


def build_clipboard_text(
    groups: Sequence[MetricGroup], bar: GrossBar, footer: str
) -> str:
    """One plain-text dump of the whole readout.

    Same idea as `LogListModel.copyAllToClipboard()`: readable as plain text,
    no markup, safe to paste into a chat message or a bug report.
    """
    lines = [
        "BACKTEST DETAIL METRICS",
        f"Gross Profit {bar.profit_text} / Gross Loss {bar.loss_text}",
        bar.caption,
        "",
    ]
    for group in groups:
        lines.append(group.label)
        lines.extend(_format_row(row) for row in group.rows)
        lines.append("")
    lines.append(footer)
    return "\n".join(lines)


def _format_row(row: MetricRow) -> str:
    suffix = f" {row.suffix}" if row.suffix else ""
    badge = f" [{row.badge_text}]" if row.badge_text else ""
    info = f" ({row.info})" if row.info else ""
    return f"  {row.title}: {row.value}{suffix}{badge}{info}"

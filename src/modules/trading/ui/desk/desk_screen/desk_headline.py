"""`EPIC-043D` — a desk's headline: the few figures its account is read for, above the detail.

@details What the account is worth, how the open positions are doing, how many there are and how
far the nearest is from liquidation, in one row above the chart (`HeadlineStrip`). Each figure is
the one the desk already shows, said once more where it is seen first: equity and unrealized PnL
from the account summary, the rest from the Positions table's own rows, so the headline can never
disagree with the table beside it (it is fed by what the table was given, not by a second read).
Each is written by the application's formatter, and the PnL carries its arrow, sign and tone.

**Today's PnL is not here.** `PRO-009` named it, but nothing in the application reads a profit
made today: the summary has the unrealized figure only. It is a figure of its own, needing a
read of the day's fills in the display time zone, so it is a later task, not a number made up
from the figures at hand (`domain-truth-rule.md`).

**The liquidation distance is derived, never computed.** The exchange reports each position's
liquidation price (`LivePosition.liquidation_price`); the distance is how far the mark is from
it, as a share of the mark, for the nearest position. A Spot desk has no positions and shows its
account value alone.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
    AssetMode,
    FuturesAccountSummary,
    SpotAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.headline_strip import (
    HeadlineFigure,
    HeadlineStrip,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import sign_tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    signed_key,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

EQUITY_KEY = "equity"
PNL_KEY = signed_key("unrealized_pnl")
POSITIONS_KEY = "positions"
LIQUIDATION_KEY = "liquidation_distance"

#: A figure the account could not give without guessing, said as a word, never as a number.
_UNKNOWN = "unknown"
#: No position, so no distance to a liquidation.
_NONE = "none"


def _unit(summary: AccountSummary) -> str:
    """The unit in the caption: the account's, not the number's (as `summary_lines` says it)."""
    if isinstance(summary, SpotAccountSummary):
        return summary.quote_asset
    multi = (
        isinstance(summary, FuturesAccountSummary)
        and summary.asset_mode is AssetMode.MULTI_ASSETS
    )
    return "USD" if multi else "USDT"


def liquidation_distance_percent(positions: Sequence[PositionRow]) -> float | None:
    """How far, in percent of its mark, the nearest position is from the liquidation price the
    exchange reported; `None` when no open position has one."""
    distances = [
        abs(position.mark_price - position.liquidation_price)
        / position.mark_price
        * Decimal(100)
        for position in positions
        if position.liquidation_price is not None and position.mark_price > 0
    ]
    return float(min(distances)) if distances else None


def headline_figures(
    summary: AccountSummary | None, positions: Sequence[PositionRow]
) -> tuple[HeadlineFigure, ...]:
    """The figures of the desk's headline; none while the account is unread."""
    if summary is None:
        return ()
    unit = _unit(summary)
    equity = HeadlineFigure(
        EQUITY_KEY,
        f"Account value ({unit})",
        write_value(ColumnKind.MONEY, float(summary.equity), EQUITY_KEY)
        if summary.equity is not None
        else _UNKNOWN,
        kind=ColumnKind.MONEY if summary.equity is not None else ColumnKind.TEXT,
    )
    if not isinstance(summary, FuturesAccountSummary):
        return (equity,)
    pnl = HeadlineFigure(
        PNL_KEY,
        f"Unrealized PnL ({unit})",
        write_value(ColumnKind.MONEY, float(summary.unrealized_pnl), PNL_KEY),
        sign_tone(summary.unrealized_pnl),
        ColumnKind.MONEY,
    )
    distance = liquidation_distance_percent(positions)
    return (
        equity,
        pnl,
        HeadlineFigure(
            POSITIONS_KEY,
            "Open positions",
            str(len(positions)),
        ),
        HeadlineFigure(
            LIQUIDATION_KEY,
            "Nearest liquidation",
            _NONE
            if distance is None
            else write_value(ColumnKind.PERCENT, distance, LIQUIDATION_KEY),
            kind=ColumnKind.TEXT if distance is None else ColumnKind.PERCENT,
        ),
    )


class DeskHeadline(QObject):
    """@brief Keeps one desk's headline strip current from what the desk already shows."""

    def __init__(self, strip: HeadlineStrip, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._strip = strip
        self._summary: AccountSummary | None = None
        self._positions: tuple[PositionRow, ...] = ()

    def on_summary(self, summary: AccountSummary | None) -> None:
        self._summary = summary
        self._show()

    def on_positions(self, positions: Sequence[PositionRow]) -> None:
        self._positions = tuple(positions)
        self._show()

    def _show(self) -> None:
        self._strip.show_figures(headline_figures(self._summary, self._positions))

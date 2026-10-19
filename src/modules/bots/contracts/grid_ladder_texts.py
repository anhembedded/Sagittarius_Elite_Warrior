"""`BOT-193` — the words that say a Grid's ladder, its summary and where the price stands.

The Bots tab and `bot show` build their lines here from `grid_ladder.py`'s read model, so both say
the same thing; each hands in its own money and price writers (the tab's formatter, the commands'
`plain_money` and `plain_price`, which call the same rules). Qt-free.

A figure the record cannot give is said so, never written as zero (`NO_PRICE_YET`, `NO_VALUE`,
`FEE_NOT_SAVED`, `LIQUIDATION_NOT_SAVED`).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.number_text import percent_text
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    LadderSummary,
    PriceMark,
    PricePosition,
    RecordedCycles,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    NO_PRICE_YET,
    NO_VALUE,
    MoneyWriter,
    PriceWriter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridSpacing,
)

#: The account's maker rate is read from the exchange, not kept in the bot's record.
FEE_NOT_SAVED = (
    "before fees: the account's maker rate is read from the exchange and is not saved"
)
LIQUIDATION_NOT_SAVED = (
    "not in the bot's record (the exchange reports it while it runs)"
)
NOT_ESTIMATED = "not estimated"
_HUNDRED = Decimal(100)
_MINUTE = 60
_HOUR = 3600
_DAY = 86_400


def percent_of(fraction: Decimal) -> str:
    """`0.0125` as `1.25%`."""
    return percent_text(float(fraction * _HUNDRED))


def signed_percent_of(fraction: Decimal) -> str:
    """`0.0125` as `+1.25%`, `-0.05` as `-5.00%`."""
    text = percent_of(fraction)
    return text if text.startswith("-") or text == "0.00%" else f"+{text}"


def age_text(seconds: int) -> str:
    """How long ago: `40 s ago`, `5 min ago`, `3 h ago`, `2 d ago` (the largest unit that fits)."""
    for unit, size in (("d", _DAY), ("h", _HOUR), ("min", _MINUTE)):
        if seconds >= size:
            return f"{seconds // size} {unit} ago"
    return f"{seconds} s ago"


def summary_line(summary: LadderSummary, money: MoneyWriter) -> str:
    """Spacing model, the smallest and largest step, the average cycle and the fee, in one line."""
    return f"{_spacing(summary)}; {_average_cycle(summary, money)}"


def brief_summary_line(summary: LadderSummary, money: MoneyWriter) -> str:
    """`summary_line` without its reasons, for a panel with little room: the full line is its tooltip."""
    name = summary.spacing.value.capitalize()
    return f"{name} spacing, {step_text(summary)}; {cycle_profit_text(summary, money)}"


def step_text(summary: LadderSummary) -> str:
    """The steps in a few words, for a row beside its label: `1.45% (top) to 1.67% (bottom)`."""
    smallest = percent_of(summary.smallest_step_fraction)
    largest = percent_of(summary.largest_step_fraction)
    if summary.spacing is GridSpacing.GEOMETRIC or smallest == largest:
        return f"{smallest} (every grid)"
    return f"{smallest} (top) to {largest} (bottom)"


def cycle_profit_text(summary: LadderSummary, money: MoneyWriter) -> str:
    """What one completed cycle earns on average, for a row beside its label."""
    if summary.average_cycle_quote is None:
        return NOT_ESTIMATED
    after = "before fees" if summary.maker_fee is None else "after fees"
    return f"about {money(summary.average_cycle_quote)} {after} (estimate)"


def recorded_average_text(recorded: RecordedCycles, money: MoneyWriter) -> str:
    """What a completed cycle booked on average, net of both legs' fees; Futures funding is not
    in it (the row's label says so). `NO_VALUE` while no cycle has completed."""
    average = recorded.average_profit
    return NO_VALUE if average is None else money(average)


def _spacing(summary: LadderSummary) -> str:
    smallest = percent_of(summary.smallest_step_fraction)
    largest = percent_of(summary.largest_step_fraction)
    if summary.spacing is GridSpacing.GEOMETRIC:
        return f"Geometric spacing: every grid steps {smallest} (designed)"
    if smallest == largest:
        return f"Arithmetic spacing: every grid steps {smallest} (designed)"
    return (
        f"Arithmetic spacing: steps from {smallest} at the top to {largest} "
        "at the bottom (designed)"
    )


def _average_cycle(summary: LadderSummary, money: MoneyWriter) -> str:
    fee = (
        FEE_NOT_SAVED
        if summary.maker_fee is None
        else f"after the {percent_of(summary.maker_fee)} maker fee on both legs"
    )
    if summary.average_cycle_quote is None:
        return f"profit per cycle: {NOT_ESTIMATED} ({fee})"
    return f"about {money(summary.average_cycle_quote)} per cycle {fee} (estimate)"


@dataclass(frozen=True, slots=True)
class PositionTexts:
    """Where the last price the bot heard stands, one text per row."""

    last_price: str
    lower_edge: str
    upper_edge: str
    stop_loss: str
    take_profit: str
    #: `None` on a venue with no liquidation price (Spot).
    liquidation: str | None


def position_texts(position: PricePosition, price: PriceWriter) -> PositionTexts:
    """The last price, its age, the distance to each edge and exit, and the liquidation price."""
    return PositionTexts(
        last_price=_last_price(position, price),
        lower_edge=_mark(position.lower, price),
        upper_edge=_mark(position.upper, price),
        stop_loss=_exit(position.stop_loss, price),
        take_profit=_exit(position.take_profit, price),
        liquidation=LIQUIDATION_NOT_SAVED if position.has_liquidation_price else None,
    )


def _last_price(position: PricePosition, price: PriceWriter) -> str:
    if position.last_price is None:
        return NO_PRICE_YET
    age = "" if position.age_seconds is None else f", {age_text(position.age_seconds)}"
    return f"{price(position.last_price)}{age}"


def _mark(mark: PriceMark, price: PriceWriter) -> str:
    if mark.distance_fraction is None:
        return price(mark.price)
    return f"{price(mark.price)} ({signed_percent_of(mark.distance_fraction)})"


def _exit(mark: PriceMark | None, price: PriceWriter) -> str:
    return "off" if mark is None else _mark(mark, price)

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
    TriggerMark,
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

#: What a net figure says about its rate: the rate of the run's start, not today's (`BOT-194`).
RATE_SOURCE = "run-start rate"
#: The account's maker rate is recorded when a run starts; a file an earlier build wrote has none.
FEE_NOT_SAVED = "before fees: no maker rate is recorded for this run (it is recorded when a run starts)"
LIQUIDATION_NOT_SAVED = (
    "not in the bot's record (the exchange reports it while it runs)"
)
NOT_ESTIMATED = "not estimated"
_HUNDRED = Decimal(100)
_MINUTE = 60
_HOUR = 3600
_DAY = 86_400


def small_money_text(value: Decimal, money: MoneyWriter) -> str:
    """`money(value)`, except that a nonzero amount the writer rounds to zero is said to be small:
    `less than 0.01`, never `0.00` (a figure that exists is not shown as zero)."""
    text = money(value)
    if value == 0 or set(text.lstrip("-")) - set("0.,"):
        return text
    cent = money(Decimal("0.01"))
    return f"less than {cent}" if value > 0 else f"more than -{cent}"


def _about(amount: str) -> str:
    """`about 1.55`, but not `about less than 0.01`."""
    return (
        amount if amount.startswith(("less than", "more than")) else f"about {amount}"
    )


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
    cycle = cycle_profit_text(summary, money)
    estimate = "" if summary.average_cycle_quote is None else " (estimate)"
    return f"{name} spacing, {step_text(summary)}; {cycle}{estimate}"


def step_text(summary: LadderSummary) -> str:
    """The steps in a few words, for a row beside its label: `1.45% to 1.67%` (top to bottom), or `1.20% each`."""
    smallest = percent_of(summary.smallest_step_fraction)
    largest = percent_of(summary.largest_step_fraction)
    if summary.spacing is GridSpacing.GEOMETRIC or smallest == largest:
        return f"{smallest} each"
    return f"{smallest} to {largest}"


def cycle_profit_text(summary: LadderSummary, money: MoneyWriter) -> str:
    """What one completed cycle earns on average, for a row beside its label."""
    if summary.average_cycle_quote is None:
        return NOT_ESTIMATED
    after = (
        "before fees" if summary.maker_fee is None else f"after fees ({RATE_SOURCE})"
    )
    return f"{_about(small_money_text(summary.average_cycle_quote, money))} {after}"


def recorded_average_text(recorded: RecordedCycles, money: MoneyWriter) -> str:
    """What a completed cycle booked on average, net of both legs' fees; Futures funding is not
    in it (the docs say so, `headless_runbook.md`). `NO_VALUE` while no cycle has completed."""
    average = recorded.average_profit
    return NO_VALUE if average is None else small_money_text(average, money)


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
        else f"after the {percent_of(summary.maker_fee)} maker fee on both legs (rate recorded at run start)"
    )
    if summary.average_cycle_quote is None:
        return f"profit per cycle: {NOT_ESTIMATED} ({fee})"
    average = small_money_text(summary.average_cycle_quote, money)
    return f"{_about(average)} per cycle {fee} (estimate)"


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


def net_figures_note(summary: LadderSummary) -> str:
    """For a table of net figures: which rate they use, or why they are blank."""
    if summary.maker_fee is None:
        return f"Net figures are blank, per cycle is {FEE_NOT_SAVED}."
    return (
        f"Net figures use the {percent_of(summary.maker_fee)} maker rate recorded when "
        "this run started, not today's rate."
    )


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


def _best_heard(trigger: TriggerMark, price: PriceWriter) -> str:
    """`BUG-276`: the best price the bot heard while waiting, so a wick between two samples shows."""
    if trigger.seen_best is None:
        return ""
    word = "lowest" if trigger.at_or_below else "highest"
    return f"; {word} price heard while waiting {price(trigger.seen_best)}"


def waiting_text(position: PricePosition, price: PriceWriter) -> str:
    """What a bot in AWAITING_RANGE says: the range it waits for, and the trigger price when the
    plan has one (`EPIC-046B`), and the price it waits on (`EPIC-044C`). The Plan's banner,
    `bot list`, `bot show` and the heartbeat say the same words."""
    # The price with how long ago it was heard: a waiting bot watches no exit, so nothing halts it
    # on a quiet feed, and a bare "now" could be hours old (`domain-truth-rule.md`).
    heard = (
        "no price heard yet"
        if position.last_price is None
        else f"last price {_last_price(position, price)}"
    )
    trigger = position.trigger
    if trigger is not None:
        # `EPIC-046B` (ADR 046 D5): one sentence whichever side the price is on, since the range
        # and the trigger together are the prices that open the entry.
        side = "≤" if trigger.at_or_below else "≥"
        return (
            f"Waiting for the price {side} {price(trigger.mark.price)} within "
            f"{price(position.lower.price)}–{price(position.upper.price)} ({heard}"
            f"{_best_heard(trigger, price)}); nothing is placed until it is"
        )
    return (
        f"Waiting for the price to enter {price(position.lower.price)}–"
        f"{price(position.upper.price)} ({heard}); nothing is placed until it does"
    )

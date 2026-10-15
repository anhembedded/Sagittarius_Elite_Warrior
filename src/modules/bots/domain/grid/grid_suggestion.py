"""`BUG-211` — a suggested Grid plan is a whole plan, and it passes the blocking checks.

A suggestion button used to write a range and nothing else, so a range that moved away from
the exits (or away from the price) produced a plan the planner's own checks refuse
(`STOP_LOSS_INSIDE_RANGE`, `TAKE_PROFIT_INSIDE_RANGE`, `PRICE_BELOW_RANGE`). The rules live
here once, for every source (ATR, Bollinger, any later one), and the panel only applies them:

  · the range holds the current price: a band that does not is recentred on the price at the
    same width, and the plan says so;
  · an exit given as a price that the new range makes invalid, or leaves outside the advised
    distance, moves to the middle of the advised distance and the plan says which, from what to
    what, and why. An exit that is `off`, or given as a percentage beyond the edge (it follows
    the edge by itself), is never touched;
  · the result is judged by `evaluate_grid`, with the thresholds unchanged, and the blocking
    codes it still carries are part of the answer (the market facts the panel holds exclude
    the account, so account-only checks are not among them).

Extension cases: a third source is one more caller of `suggest_plan` with its own band; another
exit kind is one more entry in `_EXITS`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_advice import (
    Figures,
    plain,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_advice_texts import (
    STOP_LOSS_SIDE,
    TAKE_PROFIT_SIDE,
    ExitSide,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    ExitKind,
    GridParamsError,
    exit_level_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)

_TWO = Decimal(2)
_EXITS = ((STOP_LOSS_SIDE, "stop_loss"), (TAKE_PROFIT_SIDE, "take_profit"))


@dataclass(frozen=True, slots=True)
class SuggestionRequest:
    """A source's band and the plan it is applied to."""

    #: The source's name for the user and the log: `ATR`, `Bollinger`.
    source: str
    band_lower: Decimal
    band_upper: Decimal
    #: The parameters as typed now, with the venue's terms and the market.
    inputs: BotKindInputs
    thresholds: GridThresholds


@dataclass(frozen=True, slots=True)
class ExitMove:
    """An exit price the suggestion changed, and why."""

    #: The definition's key (`stop_loss`) and the exit's name for the user (`stop loss`).
    key: str
    name: str
    old: Decimal
    new: Decimal
    reason: str

    @property
    def sentence(self) -> str:
        return (
            f"The {self.name} moved from {plain(self.old)} to {plain(self.new)}: "
            f"{self.reason}."
        )


@dataclass(frozen=True, slots=True)
class PlanSuggestion:
    """The range and exits to write, what changed besides the range, and how the plan reads."""

    source: str
    lower: Decimal
    upper: Decimal
    #: The exits to write, by definition key, only for the ones that moved.
    exits: dict[str, str]
    moves: tuple[ExitMove, ...]
    #: How the band was adapted to hold the price; `""` when it already did.
    range_note: str
    #: The codes of the constraints that still block Start, with the facts the request held.
    blocking: tuple[str, ...]

    @property
    def panel_line(self) -> str:
        """The one line the panel shows; `""` when the range was written as the band says."""
        return " ".join(
            part
            for part in (self.range_note, *(move.sentence for move in self.moves))
            if part
        )

    @property
    def log_moves(self) -> str:
        return (
            ", ".join(
                f"{move.name} {plain(move.old)}->{plain(move.new)}"
                for move in self.moves
            )
            or "none"
        )


def suggest_plan(request: SuggestionRequest) -> PlanSuggestion:
    """The plan a suggestion button writes: @see the module docstring."""
    figures = Figures.of(request.inputs.terms, request.inputs.market)
    lower, upper, note = _range_holding_the_price(request, figures)
    moves = tuple(
        move
        for exit_ in _EXITS
        if (move := _moved_exit(request, figures, exit_, (lower, upper))) is not None
    )
    config = {
        **request.inputs.config,
        "lower": plain(lower),
        "upper": plain(upper),
        **{move.key: f"price:{plain(move.new)}" for move in moves},
    }
    verdicts = evaluate_grid(
        replace(request.inputs, config=config), request.thresholds
    ).verdicts
    return PlanSuggestion(
        request.source,
        lower,
        upper,
        {move.key: config[move.key] for move in moves},
        moves,
        note,
        tuple(verdict.code for verdict in verdicts if verdict.refuses),
    )


def _range_holding_the_price(
    request: SuggestionRequest, figures: Figures
) -> tuple[Decimal, Decimal, str]:
    price = request.inputs.market.last_price
    lower, upper = figures.snap(request.band_lower), figures.snap(request.band_upper)
    if lower <= price <= upper:
        return lower, upper, ""
    half = (upper - lower) / _TWO
    tick = figures.tick
    lower = max(_to_tick(price - half, tick, ROUND_FLOOR), tick)
    upper = _to_tick(price + half, tick, ROUND_CEILING)
    note = (
        f"The {request.source} range {figures.span(request.band_lower, request.band_upper)}"
        f" does not contain the price {figures.price(price)}; it was recentred on the price "
        f"at the same width, {figures.span(lower, upper)}."
    )
    return lower, upper, note


def _moved_exit(
    request: SuggestionRequest,
    figures: Figures,
    exit_: tuple[ExitSide, str],
    range_: tuple[Decimal, Decimal],
) -> ExitMove | None:
    side, key = exit_
    try:
        level = exit_level_of(request.inputs.config, key)
    except GridParamsError:
        return None
    if level.kind is not ExitKind.PRICE:
        return None
    edge = range_[0] if side.below else range_[1]
    sign = -1 if side.below else 1
    distance = sign * (level.value - edge) / edge
    low = request.thresholds.exit_distance_low
    high = request.thresholds.exit_distance_high
    if low <= distance <= high:
        return None
    new = figures.snap(edge * (1 + sign * (low + high) / _TWO))
    advised = f"{low:.0%}–{high:.0%}"
    reason = (
        f"it was at or inside the range's {side.edge_name} limit {figures.price(edge)}"
        if distance <= 0
        else f"it was {distance:.2%} from the {side.edge_name} limit "
        f"{figures.price(edge)}, outside the advised {advised}"
    )
    middle = f"{(low + high) / _TWO:.2%}"
    return ExitMove(key, side.name, level.value, new, f"{reason}; now {middle} away")


def _to_tick(price: Decimal, tick: Decimal, rounding: str) -> Decimal:
    return (price / tick).to_integral_value(rounding=rounding) * tick

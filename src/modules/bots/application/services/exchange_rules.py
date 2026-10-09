"""`BOT-174` — the readiness rules that need the exchange's facts: pure functions.

@details Each rule is `RuleContext -> RuleOutcome`: the local state (what the plan
needs from the account, whether a start or a resume) and the exchange's facts, in,
items and advisories out. No rule reads the exchange, the clock or a port, so each
is tested with numbers and the screen, the Start use case and the Resume sequence
call the same ones (`judge_exchange`), and the button that is enabled is the click
that is accepted.

`judge_exchange` is the only place the snapshot's three states are told apart
(`exchange_facts.py`): a snapshot still being read is one item, "checking", so the
bot is not claimed ready; one that could not be read is one item naming why, never
an empty account; only a loaded one reaches `RULES`.

  · **Left from earlier runs** (advisory, a start): base a previous run kept and
    this run will not trade (`BUG-196`).
  · **Free base too small for the SELLs** (item, a resume): the exchange would
    refuse the first SELL with `-2010` after the BUY went out (`BUG-195`); refusing
    first costs nothing.
  · **Free quote too small for the ladder** (item): the opening buy and the BUY
    levels would be refused for lack of funds. It replaces the kind's
    `CAPITAL_ABOVE_BALANCE`, which compared the whole capital with a balance read
    earlier for the Connect step.

Extension cases (`architecture-rule.md` §7.2.1). Each is one function below plus
one line in `RULES`, and nothing else changes:
- the key may not trade (`ExchangeFacts.can_trade`), now a Design verdict;
- the ladder's order count against the venue's open-order limit;
- base reserved by a foreign SELL on the symbol, named when the base is short;
- the BNB balance a fee paid in BNB needs (a new fact, a new rule).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    ReadinessAdvisory,
    ReadinessFix,
    ReadinessItem,
    ReadinessStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
    ExchangeFacts,
    ExchangeLoaded,
    ExchangeSnapshot,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_needs import (
    LadderNeeds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)

_CENT = Decimal("0.01")
_ZERO = Decimal(0)

CHECKING_THE_EXCHANGE = "Checking the exchange…"
QUOTE_SHORT = "RUN_QUOTE_SHORT"
#: The verdict code the Grid editor turns into its Capital field.
CAPITAL_FIELD = "CAPITAL_ABOVE_BALANCE"


class RunPurpose(str, Enum):
    """What the ladder is being laid for."""

    START = "START"
    RESUME = "RESUME"


@dataclass(frozen=True, slots=True)
class RuleOutcome:
    """What one rule found: blocking items and non-blocking advisories."""

    items: tuple[ReadinessItem, ...] = ()
    advisories: tuple[ReadinessAdvisory, ...] = ()

    def __add__(self, other: RuleOutcome) -> RuleOutcome:
        return RuleOutcome(self.items + other.items, self.advisories + other.advisories)


@dataclass(frozen=True, slots=True)
class RuleContext:
    """Local state beside the exchange's facts: all a rule may read."""

    purpose: RunPurpose
    facts: ExchangeFacts
    #: `None` while no plan can be drawn (the parameters or the market numbers
    #: are not ready): a rule that needs the plan then says nothing.
    needs: LadderNeeds | None

    @property
    def base_available(self) -> Decimal:
        """The base the SELLs can use: what is free, and, on a resume, what the
        bot's own resting SELLs lock, since the resume cancels them first."""
        facts = self.facts
        if self.purpose is RunPurpose.RESUME:
            return facts.base_free + facts.own_sell_base
        return facts.base_free

    @property
    def quote_available(self) -> Decimal:
        facts = self.facts
        if self.purpose is RunPurpose.RESUME:
            return facts.quote_free + facts.own_buy_quote
        return facts.quote_free


type Rule = Callable[[RuleContext], RuleOutcome]


def judge_exchange(
    snapshot: ExchangeSnapshot, needs: LadderNeeds | None, purpose: RunPurpose
) -> RuleOutcome:
    """Every rule's finding over `snapshot`, or the one item its state is."""
    match snapshot:
        case ExchangeChecking():
            return RuleOutcome(
                (
                    _item(
                        "RUN_EXCHANGE_CHECKING",
                        CHECKING_THE_EXCHANGE,
                        BotRefusal.EXCHANGE_NOT_READ,
                        ReadinessFix.WAIT,
                    ),
                )
            )
        case ExchangeUnavailable(reason=reason):
            return RuleOutcome(
                (
                    _item(
                        "RUN_EXCHANGE_UNAVAILABLE",
                        f"The exchange's facts could not be read: {reason}",
                        BotRefusal.EXCHANGE_NOT_READ,
                        ReadinessFix.REFRESH_EXCHANGE,
                    ),
                )
            )
        case ExchangeLoaded(facts=facts):
            context = RuleContext(purpose, facts, needs)
            found = RuleOutcome()
            for rule in RULES:
                found = found + rule(context)
            return found


def field_verdicts(items: tuple[ReadinessItem, ...]) -> tuple[Verdict, ...]:
    """The items that are about a parameter, as the verdicts the kind's editor
    shows beside that field (`CAPITAL_ABOVE_BALANCE` on the Capital field), so a
    check that moved onto the exchange's facts still speaks where the user edits."""
    return tuple(
        Verdict(VerdictSeverity.REFUSED, item.target, item.reason)
        for item in items
        if item.code == QUOTE_SHORT and item.fix is ReadinessFix.EDIT_FIELD
    )


def earlier_runs_left(context: RuleContext) -> RuleOutcome:
    """A start tells the owner what an earlier run kept; it never refuses."""
    if context.purpose is not RunPurpose.START:
        return RuleOutcome()
    facts = context.facts
    earlier = facts.earlier_runs
    if not earlier.is_known:
        return RuleOutcome(
            advisories=(
                ReadinessAdvisory(
                    "EARLIER_RUNS_UNKNOWN",
                    "What earlier runs left on the account could not be read "
                    f"({earlier.unavailable}); the start goes on",
                ),
            )
        )
    if not earlier.is_left:
        return RuleOutcome()
    worth = (
        f"≈ {_money(earlier.quantity * context.needs.price)} {facts.quote_asset}"
        if context.needs is not None
        else f"(cost {_money(earlier.cost)} {facts.quote_asset})"
    )
    return RuleOutcome(
        advisories=(
            ReadinessAdvisory(
                "EARLIER_RUNS_LEFT",
                f"A previous run kept {_amount(earlier.quantity)} {facts.base_asset} "
                f"{worth} that this run will not trade",
            ),
        )
    )


def base_short_for_sells(context: RuleContext) -> RuleOutcome:
    """A resume sells base it must already hold free; a start buys its own."""
    needs, facts = context.needs, context.facts
    if context.purpose is not RunPurpose.RESUME or needs is None:
        return RuleOutcome()
    available = context.base_available
    if needs.base <= available:
        return RuleOutcome()
    held_elsewhere = max(facts.base_locked - facts.own_sell_base, _ZERO)
    elsewhere = (
        f"; {_amount(held_elsewhere)} {facts.base_asset} is locked by orders that "
        "are not this bot's"
        if held_elsewhere > 0
        else ""
    )
    return RuleOutcome(
        (
            _item(
                "RUN_BASE_SHORT",
                f"The resumed ladder sells {_amount(needs.base)} {facts.base_asset} "
                f"and {facts.venue_title} has {_amount(available)} {facts.base_asset} "
                f"free{elsewhere}; free the base or stop the bot",
                BotRefusal.BALANCE_TOO_SMALL,
            ),
        )
    )


def quote_short_for_ladder(context: RuleContext) -> RuleOutcome:
    """The opening buy (a start) and the BUY levels spend quote."""
    needs, facts = context.needs, context.facts
    if needs is None:
        return RuleOutcome()
    available = context.quote_available
    if needs.quote <= available:
        return RuleOutcome()
    what = (
        "The opening buy and the BUY levels"
        if context.purpose is RunPurpose.START
        else "The resumed ladder's BUY levels"
    )
    have = (
        f"{facts.venue_title} has {_money(available, ROUND_FLOOR)} "
        f"{facts.quote_asset} free"
    )
    need = f"{what} need {_money(needs.quote, ROUND_CEILING)} {facts.quote_asset}"
    if context.purpose is RunPurpose.START:
        largest = _money(needs.capital * available / needs.quote, ROUND_FLOOR)
        return RuleOutcome(
            (
                _item(
                    QUOTE_SHORT,
                    f"{need} and {have}; lower the capital to at most {largest}",
                    BotRefusal.BALANCE_TOO_SMALL,
                    ReadinessFix.EDIT_FIELD,
                    CAPITAL_FIELD,
                ),
            )
        )
    return RuleOutcome(
        (
            _item(
                QUOTE_SHORT,
                f"{need} and {have}; free the quote or stop the bot",
                BotRefusal.BALANCE_TOO_SMALL,
            ),
        )
    )


#: The rules, in the order their findings are listed. A new check is one more entry.
RULES: tuple[Rule, ...] = (
    earlier_runs_left,
    base_short_for_sells,
    quote_short_for_ladder,
)


def _item(
    code: str,
    reason: str,
    refusal: BotRefusal,
    fix: ReadinessFix = ReadinessFix.NONE,
    target: str = "",
) -> ReadinessItem:
    return ReadinessItem(ReadinessStep.RUN, code, reason, fix, refusal, target)


def _amount(value: Decimal) -> str:
    """A base quantity without trailing zeros or an exponent."""
    return f"{value.normalize():f}"


def _money(value: Decimal, rounding: str = ROUND_FLOOR) -> str:
    return f"{value.quantize(_CENT, rounding=rounding):f}"

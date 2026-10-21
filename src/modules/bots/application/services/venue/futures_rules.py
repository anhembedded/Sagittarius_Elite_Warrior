"""`EPIC-039E` — the readiness rules for a Futures venue: pure functions, one each.

@details The Futures counterpart of `exchange_rules.py`. Each rule is
`FuturesRuleContext -> RuleOutcome`; `judge_futures` runs `FUTURES_RULES` over a loaded
snapshot and tells the other two states apart exactly as `judge_exchange` does. The Spot
rules never see a Futures snapshot and these never see a Spot one: `venue_rules.py` picks
the set by the venue's profile, no rule branches on a market.

  · **Position mode not One-way** (item): the account is in Hedge Mode.
  · **Multi-Assets mode** (item, `BUG-260`): the exchange refuses isolated margin under it
    (`-4168`), and this app trades isolated only. Its balance is every asset in USD, so the
    margin rule stays silent beside it rather than quote a figure that is not the contract's.
  · **A position already stands** (item, a start): a bot starts on a flat symbol, and the
    exchange's position is then not the bot's. A resume's own/foreign split needs the
    exposure book (`EPIC-039D`) and says nothing here.
  · **Leverage above the bracket** (item): the symbol allows less leverage at the notional
    the ladder can reach.
  · **Margin short for the ladder** (item, a start): the plan's worst-case initial margin
    against the available margin. A resume's margin waits for the same book, since the
    bot's own resting orders hold some.

`SYMBOL_NOT_TRADING` and `KEY_CANNOT_TRADE` are Design verdicts of the kind (`grid_account_checks.py`,
`symbol_status_gate.py`) and run on every profile; they are not repeated here.

Extension cases: a new check is one function below and one line in `FUTURES_RULES`;
Cross margin's maintenance-margin check, the venue's open-order limit.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.exchange_rules import (
    RuleOutcome,
    RunPurpose,
    item,
    money,
    not_loaded_outcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesFacts,
    FuturesLoaded,
    FuturesSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_needs import (
    FuturesNeeds,
    bracket_below_leverage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AssetMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    PositionMode,
)

MARGIN_SHORT = "RUN_MARGIN_SHORT"
FOREIGN_POSITION = "RUN_FOREIGN_POSITION"
LEVERAGE_ABOVE_BRACKET = "RUN_LEVERAGE_ABOVE_BRACKET"
POSITION_MODE_NOT_ONE_WAY = "RUN_POSITION_MODE_NOT_ONE_WAY"
MULTI_ASSETS_MODE = "RUN_MULTI_ASSETS_MODE"


@dataclass(frozen=True, slots=True)
class FuturesRuleContext:
    purpose: RunPurpose
    facts: FuturesFacts
    #: `None` while no plan can be drawn: a rule that needs the plan then says nothing.
    needs: FuturesNeeds | None


type FuturesRule = Callable[[FuturesRuleContext], RuleOutcome]


def judge_futures(
    snapshot: FuturesSnapshot, needs: FuturesNeeds | None, purpose: RunPurpose
) -> RuleOutcome:
    """Every Futures rule's finding over `snapshot`, or the one item its state is."""
    if not isinstance(snapshot, FuturesLoaded):
        return not_loaded_outcome(snapshot)
    context = FuturesRuleContext(purpose, snapshot.facts, needs)
    found = RuleOutcome()
    for rule in FUTURES_RULES:
        found = found + rule(context)
    return found


def position_mode_not_one_way(context: FuturesRuleContext) -> RuleOutcome:
    facts = context.facts
    if facts.position_mode is PositionMode.ONE_WAY:
        return RuleOutcome()
    return RuleOutcome(
        (
            item(
                POSITION_MODE_NOT_ONE_WAY,
                f"{facts.venue_title} is in Hedge Mode and this app trades One-way only; "
                "switch the account to One-way Mode in the exchange (the app never changes it)",
                BotRefusal.VENUE_NOT_READY,
            ),
        )
    )


def multi_assets_mode(context: FuturesRuleContext) -> RuleOutcome:
    facts = context.facts
    if facts.asset_mode is not AssetMode.MULTI_ASSETS:
        return RuleOutcome()
    return RuleOutcome(
        (
            item(
                MULTI_ASSETS_MODE,
                f"{facts.venue_title} is in Multi-Assets Mode, which does not allow isolated "
                "margin, and this app trades isolated only. Turn off Multi-Assets Mode in "
                "Binance Futures preferences (the app never changes it; a change shows here within "
                "five minutes)",
                BotRefusal.VENUE_NOT_READY,
            ),
        )
    )


def foreign_position(context: FuturesRuleContext) -> RuleOutcome:
    facts = context.facts
    if context.purpose is not RunPurpose.START or facts.position == 0:
        return RuleOutcome()
    way = "long" if facts.position > 0 else "short"
    return RuleOutcome(
        (
            item(
                FOREIGN_POSITION,
                f"{facts.symbol} already holds a {way} position of {abs(facts.position):f} "
                f"on {facts.venue_title}; a bot starts on a flat symbol, so close it first",
                BotRefusal.VENUE_NOT_READY,
            ),
        )
    )


def leverage_above_bracket(context: FuturesRuleContext) -> RuleOutcome:
    needs, facts = context.needs, context.facts
    if needs is None:
        return RuleOutcome()
    bracket = bracket_below_leverage(
        facts.brackets, needs.worst_case_notional, needs.leverage
    )
    if bracket is None:
        return RuleOutcome()
    return RuleOutcome(
        (
            item(
                LEVERAGE_ABOVE_BRACKET,
                f"{needs.leverage}x is above the {bracket.initial_leverage}x "
                f"{facts.venue_title} allows {facts.symbol} at a notional of "
                f"{money(needs.worst_case_notional, ROUND_CEILING)} (bracket "
                f"{bracket.bracket}); lower the leverage or the capital",
                BotRefusal.PARAMETERS_REFUSED,
            ),
        )
    )


def margin_short_for_ladder(context: FuturesRuleContext) -> RuleOutcome:
    needs, facts = context.needs, context.facts
    if context.purpose is not RunPurpose.START or needs is None:
        return RuleOutcome()
    if facts.asset_mode is AssetMode.MULTI_ASSETS:
        return RuleOutcome()
    if needs.initial_margin <= facts.available_margin:
        return RuleOutcome()
    return RuleOutcome(
        (
            item(
                MARGIN_SHORT,
                f"The ladder's worst case needs {money(needs.initial_margin, ROUND_CEILING)} "
                f"{facts.quote_asset} of initial margin and {facts.venue_title} has "
                f"{money(facts.available_margin, ROUND_FLOOR)} {facts.quote_asset} available; "
                "lower the capital or the leverage, or add margin",
                BotRefusal.BALANCE_TOO_SMALL,
            ),
        )
    )


#: The rules, in the order their findings are listed. A new check is one more entry.
FUTURES_RULES: tuple[FuturesRule, ...] = (
    position_mode_not_one_way,
    multi_assets_mode,
    foreign_position,
    leverage_above_bracket,
    margin_short_for_ladder,
)

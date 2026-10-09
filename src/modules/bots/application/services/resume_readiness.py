"""`BOT-174` — what stands in the way of resuming a HALTED Grid, from the exchange's facts.

@details A resume lays no opening buy: its SELL levels sell base the account must
already hold free, and its BUY levels spend quote (`grid_resume_plan.py`). The
exchange refuses a SELL the free base does not cover with `-2010`, after the BUY
went out (`BUG-195`), so the rules refuse first, naming both numbers.

`assess_resume` is the pure judgement, called by the Bots screen with the snapshot
it holds (the Resume button's reason) and by `ResumeReadinessReader` with a
snapshot read at the click (the Resume use case's refusal): the same rules, the
same words (`exchange_rules.py`).

The inventory the plan is sized to is the bot's own record of it. The proposal
that follows derives it again from the exchange; a disagreement between the two is
what `BUG-195` has not yet explained, and is outside this check.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exchange_facts_reader import (
    ExchangeFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exchange_rules import (
    RuleOutcome,
    RunPurpose,
    judge_exchange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    GridRuntimeCodecError,
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.ladder_needs import (
    resume_ladder_needs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.planner_numbers import (
    read_planner_numbers,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness_assessment import (
    MARKET_NOT_READ,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    ReadinessFix,
    ReadinessItem,
    ReadinessStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_needs import (
    LadderNeeds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
    OwnerInventory,
)

logger = logging.getLogger("App.Bots.Readiness")

_UNREADABLE_RECORD = ReadinessItem(
    ReadinessStep.RUN,
    "RUN_RECORD_UNREADABLE",
    "The bot's record of its run cannot be read, so what the resume needs is not known",
    ReadinessFix.NONE,
    BotRefusal.UNREADABLE,
)


@dataclass(frozen=True, slots=True)
class ResumeInputs:
    config: Mapping[str, str]
    #: `None` while the market numbers are being read.
    market: PlannerMarket | None
    inventory: OwnerInventory
    exchange: ExchangeSnapshot


def assess_resume(inputs: ResumeInputs) -> RuleOutcome:
    """The resume's findings. It fails closed, as Start does: a ladder that
    cannot be drawn (the market numbers still being read, unreadable, or
    parameters that do not parse) is one named item, never a silent pass."""
    needs, unplanned = _needs_of(inputs)
    outcome = judge_exchange(inputs.exchange, needs, RunPurpose.RESUME)
    return RuleOutcome(unplanned + outcome.items, outcome.advisories)


def _needs_of(
    inputs: ResumeInputs,
) -> tuple[LadderNeeds | None, tuple[ReadinessItem, ...]]:
    market = inputs.market
    if market is None:
        return None, (
            _plan_item("RUN_PLAN_READING", MARKET_NOT_READ, ReadinessFix.WAIT),
        )
    if market.terms is None or market.market is None:
        return None, (
            _plan_item(
                "RUN_PLAN_UNREADABLE",
                f"The resumed ladder cannot be drawn: {market.problem}",
                ReadinessFix.NONE,
            ),
        )
    needs = resume_ladder_needs(
        inputs.config, market.terms, market.market.last_price, inputs.inventory
    )
    if needs is None:
        return None, (
            _plan_item(
                "RUN_PLAN_UNREADABLE",
                "The resumed ladder cannot be drawn: the bot's parameters cannot be read",
                ReadinessFix.NONE,
            ),
        )
    return needs, ()


def _plan_item(code: str, reason: str, fix: ReadinessFix) -> ReadinessItem:
    return ReadinessItem(
        ReadinessStep.RUN, code, reason, fix, BotRefusal.VENUE_NOT_READY
    )


class ResumeReadinessReader:
    """@brief What is left before `stored` may resume, from the world as it is now."""

    def __init__(
        self,
        facts: ExchangeFactsReader,
        ports: IVenueTradingPorts,
        caps: OwnerBudgetCaps,
    ) -> None:
        self._facts = facts
        self._ports = ports
        self._caps = caps

    def read(self, stored: StoredBot) -> RuleOutcome:
        bot = stored.bot
        definition = bot.definition
        inventory = _inventory_of(stored)
        if inventory is None:
            return RuleOutcome((_UNREADABLE_RECORD,))
        numbers = read_planner_numbers(
            self._ports, self._caps, definition.venue, definition.symbol
        )
        market = (
            PlannerMarket(None, None, None, None, numbers)
            if isinstance(numbers, str)
            else PlannerMarket(numbers[0], numbers[1], None, None)
        )
        outcome = assess_resume(
            ResumeInputs(definition.config, market, inventory, self._facts.read(bot))
        )
        logger.debug(
            "Bot %s resume readiness: %d thing(s) left (%s)",
            bot.bot_id.value,
            len(outcome.items),
            ", ".join(item.code for item in outcome.items) or "none",
        )
        return outcome


def _inventory_of(stored: StoredBot) -> OwnerInventory | None:
    if not stored.runtime:
        return OwnerInventory(Decimal(0), Decimal(0))
    try:
        runtime = decode_runtime(stored.runtime)
    except GridRuntimeCodecError:
        return None
    return OwnerInventory(runtime.inventory, runtime.cost)

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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
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
    #: `None` while the symbol's terms or price are not read: no plan can be drawn.
    terms: ExchangeTerms | None
    price: Decimal | None
    inventory: OwnerInventory
    exchange: ExchangeSnapshot


def assess_resume(inputs: ResumeInputs) -> RuleOutcome:
    needs = (
        resume_ladder_needs(inputs.config, inputs.terms, inputs.price, inputs.inventory)
        if inputs.terms is not None and inputs.price is not None
        else None
    )
    return judge_exchange(inputs.exchange, needs, RunPurpose.RESUME)


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
        terms, price = (
            (None, None)
            if isinstance(numbers, str)
            else (numbers[0], numbers[1].last_price)
        )
        outcome = assess_resume(
            ResumeInputs(
                definition.config,
                terms,
                price,
                inventory,
                self._facts.read(bot),
            )
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

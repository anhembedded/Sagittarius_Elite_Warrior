"""`EPIC-029B` — the seam every kind of bot plugs into (ADR D2, architecture rule §7.2.1).

A kind answers three questions about its parameters and supplies the one thing
that runs it:

  · `kind_id` — the stable name the store writes into each definition;
  · `validate()` — a verdict per check (the user's rule: parameters are the
    user's; the kind computes and judges, it never fixes them);
  · `overlay()` — what the bot's chart draws;
  · `executor_factory()` — what builds the executor that runs one bot.

@par Extension cases (only Grid is built: `EPIC-029C`, `EPIC-029E`)
  · **Signal** — a strategy's signals drive a bot instead of a desk card
    (`EPIC-029L`); validate checks the strategy's parameter schema.
  · **DCA** — scheduled buys with a safety-order ladder (`EPIC-029L`).
  · **Futures Grid** — the same planner with leverage, a liquidation guard and
    long, short or neutral modes (`EPIC-029K`); validate adds the liquidation
    distance.
  · **Trailing Grid** — a ladder that moves its range with the price; the
    overlay grows a range history.

Each is a new class implementing this ABC and one registration; the shell, the
store and the lifecycle do not change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict


class IBotKind(ABC):
    """One kind of bot: its name, its judgement, its chart and its executor."""

    @property
    @abstractmethod
    def kind_id(self) -> str:
        """The stable name written into every definition of this kind."""

    @abstractmethod
    def validate(self, inputs: BotKindInputs) -> tuple[Verdict, ...]:
        """One verdict per check. Never raises on bad parameters: a parameter
        that cannot be parsed is itself a REFUSED verdict."""

    @abstractmethod
    def overlay(self, inputs: BotKindInputs) -> BotOverlay:
        """The lines the bot's chart draws for these parameters."""

    @abstractmethod
    def executor_factory(self) -> IBotExecutorFactory:
        """What builds the executor that runs one bot of this kind."""

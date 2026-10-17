"""`EPIC-029B` — the seam every kind of bot plugs into (ADR D2, architecture rule §7.2.1).

A kind answers three questions about its parameters and supplies the one thing
that runs it:

  · `kind_id` — the stable name the store writes into each definition;
  · `supported_profiles()` — the markets it can run on (`EPIC-039A`);
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

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    RecoveryLayer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict


class IBotKind(ABC):
    """One kind of bot: its name, its judgement, its chart and its executor."""

    @property
    @abstractmethod
    def kind_id(self) -> str:
        """The stable name written into every definition of this kind."""

    @abstractmethod
    def supported_profiles(self) -> frozenset[MarketType]:
        """The markets this kind can run on, declared by the kind and never inferred, so a
        new kind states its markets on purpose (`EPIC-039A`).

        Declared and tested now, **not yet read** by the code that decides whether a bot may
        run on a venue: that is `bot_profile_of`, which consults `BOT_MARKETS` alone, the
        build-wide ceiling. `EPIC-039H` makes `bot_profile_of` take the kind, so a venue
        qualifies only when its market is here *and* in `BOT_MARKETS`."""

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

    def recovery_layer(self) -> RecoveryLayer:
        """The kind's layer of the halt-recovery policy (`EPIC-042`, ADR 042 §2.3): reasons only
        this kind has, changes to a common one, or reasons it withdraws. Concrete and empty by
        default, so a kind that recovers nothing of its own declares nothing and no implementer
        changes (a port gaining an `@abstractmethod` would change every one, `BUG-026`)."""
        return RecoveryLayer(self.kind_id)

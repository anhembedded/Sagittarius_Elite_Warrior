"""`EPIC-029B` — the seam every kind of bot plugs into (ADR D2, architecture rule §7.2.1).

A kind answers three questions about its parameters and supplies the one thing
that runs it:

  · `kind_id` — the stable name the store writes into each definition;
  · `supported_profiles()` — the markets it can run on (`EPIC-039A`);
  · `validate()` — a verdict per check (the user's rule: parameters are the
    user's; the kind computes and judges, it never fixes them);
  · `parameter_problem()` — whether a set of parameters being changed can be stored, judged
    without the exchange (`bot edit`, `EPIC-038L`);
  · `overlay()` — what the bot's chart draws;
  · `executor_factory()` — what builds the executor that runs one bot;
  · `backtester()` — what replays the kind's parameters over stored candles (`EPIC-040B`).

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
from collections.abc import Collection, Mapping

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import JsonValue
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    IKindBacktester,
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

    def parameter_problem(
        self, config: Mapping[str, str], changed: Collection[str]
    ) -> str | None:
        """Why `config`, in which the keys `changed` were just set, cannot be stored; `None` when it can.

        Judged from the parameters alone: no exchange, no account, no price. That is `bot edit`'s
        question (a bot at rest is edited without a venue session), and a bot is still judged against
        the exchange when it starts (`validate`), so passing here promises a readable value, not a
        startable bot. An unknown key is refused. Only `changed` is judged: a key the bot already
        held is not this edit's doing. A sentence for the operator; it may quote the offending value (`GridParamsError` does), which is harmless because a setting's value is limited to 1-64 characters of `[A-Za-z0-9_.:+-]` (`ParameterSetting`) before it reaches here.

        Concrete and **closed by default**, so a kind that has not declared its parameters is
        edited by no command line and no implementer changes (a port gaining an `@abstractmethod`
        would change every one, `BUG-026`)."""
        return (
            f"a bot of kind {self.kind_id!r} declares no parameters that a command line may "
            "change; use the Bots tab"
        )

    def exposure_left(
        self, symbol: str, runtime: Mapping[str, JsonValue]
    ) -> str | None:
        """What a bot of this kind, at rest, still holds according to its record, in a sentence; `None` when nothing (`EPIC-045B`).

        `bot delete` on the running host asks it: forgetting a bot that still holds a base asset, a
        live order or an order it owes would orphan them, and a host delete has no dialog. It can
        only refuse, never permit a delete the lifecycle table refuses, and the record is not the
        exchange: a `None` promises nothing the exchange did not say, a sentence keeps the bot.
        `symbol` names the pair, because a figure in the quote asset means nothing without it. An empty `runtime` is a bot that never ran.

        Concrete and **closed by default**: a kind that has not declared how to read its record is
        never deleted by a command line (the Bots tab still deletes it) and no implementer changes
        (a port gaining an `@abstractmethod` would change every one, `BUG-026`)."""
        if not runtime:
            return None
        return (
            f"a bot of kind {self.kind_id!r} declares no way to tell what it still holds; "
            "delete it in the Bots tab"
        )

    def recovery_layer(self) -> RecoveryLayer:
        """The kind's layer of the halt-recovery policy (`EPIC-042`, ADR 042 §2.3): reasons only
        this kind has, changes to a common one, or reasons it withdraws. Concrete and empty by
        default, so a kind that recovers nothing of its own declares nothing and no implementer
        changes (a port gaining an `@abstractmethod` would change every one, `BUG-026`)."""
        return RecoveryLayer(self.kind_id)

    def backtester(self) -> IKindBacktester | None:
        """The kind's backtest, or `None` when it has none (`EPIC-040B`). Concrete and `None` by
        default, so a kind with no backtest declares nothing and no implementer changes (a port
        gaining an `@abstractmethod` would change every one, `BUG-026`)."""
        return None

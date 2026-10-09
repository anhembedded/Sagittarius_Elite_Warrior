"""`EPIC-034H` — the one function that says what is left before a bot starts.

`assess_readiness` is the single place the three steps are judged. The Bots
screen calls it with what it already holds (the account the Connect step read,
the planner's market numbers, the parameters on screen); the Start use case
calls it, through `BotReadinessReader`, with numbers read afresh at the click.
Same function, same words, so the button that is enabled is the click that is
accepted, and a refusal after the click is a refusal the screen could not have
shown (a race, reported in the same words).

  · **Connect** — the venue's account was read. Reading and a failed read are
    each one item; a failed read says what to do and offers Retry.
  · **Design** — only once connected, every constraint on the plan holds. The
    kind's own judgement (`IBotKind.validate`, with the account) supplies one
    item per blocking verdict; advice is never an item.
  · **Run** — nothing else stands in the way: the venue trades Spot, no other
    bot is active (ADR D20), nobody else holds the symbol, the owner budget
    fits trading's caps. These are listed whether or not an earlier step is
    open, so the count is what is known to be left.

A step is `WAITING` when it has nothing to do because an earlier one is open.
What cannot be known before an order, because it needs the exchange to answer
(reconciling the account, registering the budget), stays Start's own refusal.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exchange_rules import (
    RuleOutcome,
    RunPurpose,
    judge_exchange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.ladder_needs import (
    start_ladder_needs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
    ReadinessFix,
    ReadinessItem,
    ReadinessStep,
    StepReadiness,
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
    ExchangeSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
    BotKindInputs,
)

MARKET_NOT_READ = "The market numbers for this symbol are still being read."
#: What the first reading of the account says.
READING_THE_ACCOUNT = "Reading the account…"


class ConnectionState(str, Enum):
    READING = "READING"
    FAILED = "FAILED"
    CONNECTED = "CONNECTED"


@dataclass(frozen=True, slots=True)
class ConnectionRead:
    """The Connect step's answer, as the assessment needs it."""

    state: ConnectionState
    #: The venue by its title, never its identifier.
    venue_title: str
    #: What a connected account says about money and permission.
    account: AccountView | None = None
    #: Why a failed read failed, and what to do, without how to read again.
    reason: str = ""


@dataclass(frozen=True, slots=True)
class RunFacts:
    """The Run step's facts; each is empty when it holds."""

    #: Why the venue cannot run a Spot Grid.
    venue_problem: str = ""
    #: The id of another bot that is still active (ADR D20).
    other_active_bot: str = ""
    #: Who else holds the symbol's lease.
    lease_holder: str = ""
    #: Which cap the owner budget exceeds.
    budget_problem: str = ""


@dataclass(frozen=True, slots=True)
class ReadinessInputs:
    #: `None` when no kind in the catalog has `kind_id`.
    kind: IBotKind | None
    kind_id: str
    symbol: str
    #: The parameters that would run.
    config: Mapping[str, str]
    connection: ConnectionRead
    #: `None` while the market numbers are being read.
    market: PlannerMarket | None
    run: RunFacts
    #: `BOT-174` — what the exchange says; still being asked until it answers.
    exchange: ExchangeSnapshot = field(default_factory=ExchangeChecking)


def assess_readiness(inputs: ReadinessInputs) -> BotReadiness:
    connect = _connect_items(inputs.connection)
    connected = inputs.connection.state is ConnectionState.CONNECTED
    # A venue that cannot run a Spot Grid has numbers to judge no plan by: the
    # Run step names it once and Design waits.
    designable = connected and not inputs.run.venue_problem
    design = _design_items(inputs) if designable else ()
    # The exchange's facts are judged against a plan that stands: Connect, the
    # Run step's venue item and Design already say what blocks one, and the
    # facts would repeat one cause as two.
    exchange = _exchange_outcome(inputs) if designable and not design else RuleOutcome()
    run = _run_items(inputs, connected) + exchange.items
    return BotReadiness(
        (
            StepReadiness(
                ReadinessStep.CONNECT,
                StepStatus.OPEN if connect else StepStatus.DONE,
                connect,
            ),
            StepReadiness(
                ReadinessStep.DESIGN,
                _status(design, waiting=not designable),
                design,
            ),
            StepReadiness(
                ReadinessStep.RUN,
                _status(run, waiting=bool(connect or design)),
                run,
            ),
        ),
        exchange.advisories,
    )


def _exchange_outcome(inputs: ReadinessInputs) -> RuleOutcome:
    """The exchange rules over the plan a Start would place."""
    market = inputs.market
    needs = (
        start_ladder_needs(inputs.config, market.terms, market.market.last_price)
        if market is not None and market.terms and market.market
        else None
    )
    return judge_exchange(inputs.exchange, needs, RunPurpose.START)


def _status(items: tuple[ReadinessItem, ...], *, waiting: bool) -> StepStatus:
    if items:
        return StepStatus.OPEN
    return StepStatus.WAITING if waiting else StepStatus.DONE


def _connect_items(connection: ConnectionRead) -> tuple[ReadinessItem, ...]:
    if connection.state is ConnectionState.CONNECTED:
        return ()
    if connection.state is ConnectionState.READING:
        return (
            ReadinessItem(
                ReadinessStep.CONNECT,
                "CONNECT_READING",
                f"{connection.venue_title}: {READING_THE_ACCOUNT}",
                ReadinessFix.WAIT,
                BotRefusal.VENUE_NOT_READY,
            ),
        )
    return (
        ReadinessItem(
            ReadinessStep.CONNECT,
            "CONNECT_FAILED",
            f"{connection.venue_title}: {connection.reason}",
            ReadinessFix.RETRY_CONNECTION,
            BotRefusal.VENUE_NOT_READY,
        ),
    )


def _design_items(inputs: ReadinessInputs) -> tuple[ReadinessItem, ...]:
    def item(
        code: str, reason: str, fix: ReadinessFix, target: str = ""
    ) -> tuple[ReadinessItem, ...]:
        return (
            ReadinessItem(
                ReadinessStep.DESIGN,
                code,
                reason,
                fix,
                BotRefusal.PARAMETERS_REFUSED,
                target,
            ),
        )

    market = inputs.market
    if inputs.kind is None:
        return item(
            "DESIGN_KIND_UNKNOWN",
            f"No kind of bot is called {inputs.kind_id!r}.",
            ReadinessFix.NONE,
        )
    if market is None:
        return item("DESIGN_MARKET_READING", MARKET_NOT_READ, ReadinessFix.WAIT)
    if market.terms is None or market.market is None:
        return item(
            "DESIGN_MARKET_UNREADABLE",
            f"The plan cannot be judged: {market.problem}",
            ReadinessFix.NONE,
        )
    verdicts = inputs.kind.validate(
        BotKindInputs(
            inputs.config, market.terms, market.market, inputs.connection.account
        )
    )
    return tuple(
        ReadinessItem(
            ReadinessStep.DESIGN,
            verdict.code,
            verdict.reason,
            ReadinessFix.EDIT_FIELD,
            BotRefusal.PARAMETERS_REFUSED,
            verdict.code,
        )
        for verdict in verdicts
        if verdict.refuses
    )


def _run_items(inputs: ReadinessInputs, connected: bool) -> tuple[ReadinessItem, ...]:
    run = inputs.run

    def item(
        code: str,
        reason: str,
        refusal: BotRefusal,
        fix: ReadinessFix = ReadinessFix.NONE,
        target: str = "",
    ) -> ReadinessItem:
        return ReadinessItem(ReadinessStep.RUN, code, reason, fix, refusal, target)

    items: list[ReadinessItem] = []
    # An unreachable venue is already Connect's item; saying it twice would
    # count one cause as two things left.
    if connected and run.venue_problem:
        items.append(
            item("RUN_VENUE_NOT_READY", run.venue_problem, BotRefusal.VENUE_NOT_READY)
        )
    if run.other_active_bot:
        items.append(
            item(
                "RUN_OTHER_BOT_ACTIVE",
                f"Bot {run.other_active_bot} is still active; stop it before "
                "starting another",
                BotRefusal.ONE_RUNNING_BOT_DURING_FAST_TRACK,
                ReadinessFix.STOP_OTHER_BOT,
                run.other_active_bot,
            )
        )
    if run.lease_holder:
        items.append(
            item(
                "RUN_SYMBOL_LEASED",
                f"{inputs.symbol} is held by another owner",
                BotRefusal.SYMBOL_LEASED,
            )
        )
    if run.budget_problem:
        items.append(
            item(
                "RUN_BUDGET_REFUSED",
                run.budget_problem,
                BotRefusal.BUDGET_REFUSED,
                ReadinessFix.EDIT_FIELD,
                "TOO_MANY_LEVELS",
            )
        )
    return tuple(items)

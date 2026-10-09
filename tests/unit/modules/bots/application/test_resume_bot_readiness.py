"""`BOT-174` — a resume from HALTED is refused, before anything is queued, when the
account's free base cannot cover the SELLs its ladder lays (`BUG-195`).

@details The exchange refuses the first SELL of such a ladder with `-2010` after
the BUY went out and the run halts again. The Resume use case reads the exchange's
facts and judges them with the rules the Bots screen shows on the Resume button, so
the two cannot disagree. A paused bot's resume lays no ladder and is not gated.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness_assessment import (
    MARKET_NOT_READ,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.resume_readiness import (
    ResumeInputs,
    ResumeReadinessReader,
    assess_resume,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
    ResumeBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    ReadinessFix,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot, BotLifecycle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import (
    OrderType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    readiness_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
    SYMBOL,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    TERMS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs as grid_inputs,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.exchange_facts_fixtures import (
    loaded,
)

#: The ladder the world's parameters draw at 121 sells 2 × 2.066 BTC.
HELD = Decimal("4.132")


class _Runner(IBotRunner):
    def __init__(self) -> None:
        self.resumed: list[str] = []

    def start(self, bot_id: str):  # type: ignore[no-untyped-def]
        raise AssertionError("a resume never starts")

    def pause(self, bot_id: str) -> None: ...

    def resume(self, bot_id: str) -> None:
        self.resumed.append(bot_id)

    def stop(self, bot_id: str, base: BaseHandling) -> None: ...

    def confirm_resume(self, bot_id: str) -> None: ...

    def has_resume_proposal(self, bot_id: str) -> bool:
        return False


def _halt(world: ReadinessWorld, state: BotLifecycleState) -> None:
    stored = world.store.load(BotId(BOT))
    bot = Bot(
        stored.bot.bot_id,
        stored.bot.definition,
        BotLifecycle(state),
        stored.bot.created_at,
    )
    runtime = GridRuntime((), inventory=HELD, cost=Decimal(500))
    world.store.save(StoredBot(bot, encode_runtime(runtime)))


def _hold(world: ReadinessWorld, base_free: str, base_locked: str = "0") -> None:
    status = world.holdings.check_connection()
    world.holdings.answer_with(
        replace(
            status,
            holdings=(
                SpotHolding(
                    "BTC", Decimal(base_free), Decimal(base_locked), Decimal(0)
                ),
                *status.holdings,  # type: ignore[misc]
            ),
        )
    )


def _handler(world: ReadinessWorld, runner: _Runner) -> ResumeBotCommandHandler:
    return ResumeBotCommandHandler(
        world.store,
        runner,
        ResumeReadinessReader(world.facts, world.ports, world.caps),
    )


def _resume(world: ReadinessWorld, runner: _Runner):  # type: ignore[no-untyped-def]
    return _handler(world, runner).execute(ResumeBotCommand(BOT))


@pytest.fixture
def world() -> ReadinessWorld:
    made = readiness_world()
    _halt(made, BotLifecycleState.HALTED)
    return made


def test_a_resume_whose_sells_the_free_base_covers_is_queued(
    world: ReadinessWorld,
) -> None:
    _hold(world, "4.132")
    runner = _Runner()

    result = _resume(world, runner)

    assert result.accepted, result.message
    assert runner.resumed == [BOT]


def test_a_resume_one_step_short_of_base_is_refused_and_nothing_is_queued(
    world: ReadinessWorld,
) -> None:
    _hold(world, "4.131")
    runner = _Runner()

    result = _resume(world, runner)

    assert not result.accepted
    assert result.refusal is BotRefusal.BALANCE_TOO_SMALL
    assert result.message.startswith("Resume is blocked: ")
    assert "sells 4.132 BTC" in result.message
    assert "has 4.131 BTC free" in result.message
    assert runner.resumed == []


def test_the_base_the_bots_own_resting_sells_lock_counts_as_it_cancels_them_first(
    world: ReadinessWorld,
) -> None:
    _hold(world, "1.132", base_locked="3")
    activity = world.ports.get(
        world.store.load(BotId(BOT)).bot.definition.venue
    ).account_activity
    assert isinstance(activity, FakeAccountActivity)
    activity.holding_open_orders(
        [
            Order(
                ClientOrderId(f"SEW-{BOT}-aaaaaaaaaa"),
                SYMBOL,
                OrderSide.SELL,
                OrderType.LIMIT,
                Decimal(3),
                price=Decimal(130),
            )
        ]
    )
    runner = _Runner()

    result = _resume(world, runner)

    assert result.accepted, result.message


def test_base_locked_by_someone_elses_order_is_named_when_it_is_the_shortfall(
    world: ReadinessWorld,
) -> None:
    _hold(world, "1.132", base_locked="3")

    result = _resume(world, _Runner())

    assert not result.accepted
    assert "3 BTC is locked by orders that are not this bot's" in result.message


def test_a_snapshot_that_could_not_be_read_refuses_the_resume_naming_why(
    world: ReadinessWorld,
) -> None:
    activity = world.ports.get(
        world.store.load(BotId(BOT)).bot.definition.venue
    ).account_activity
    assert isinstance(activity, FakeAccountActivity)
    activity.open_orders_raise(ConnectionError("rate limited"))
    runner = _Runner()

    result = _resume(world, runner)

    assert result.refusal is BotRefusal.EXCHANGE_NOT_READ
    assert "rate limited" in result.message
    assert runner.resumed == []


def test_a_paused_bots_resume_lays_no_ladder_and_is_not_gated(
    world: ReadinessWorld,
) -> None:
    _halt(world, BotLifecycleState.PAUSED)
    _hold(world, "0")
    runner = _Runner()

    result = _resume(world, runner)

    assert result.accepted
    assert runner.resumed == [BOT]
    assert world.session.earlier_runs_requests == []


# --- fail closed: a ladder that cannot be drawn is a named item, as in Start ----


def test_a_resume_whose_market_numbers_are_still_being_read_waits() -> None:
    outcome = assess_resume(
        ResumeInputs(CONFIG, None, OwnerInventory(HELD, Decimal(500)), loaded())
    )

    (item,) = outcome.items
    assert (item.code, item.fix) == ("RUN_PLAN_READING", ReadinessFix.WAIT)
    assert item.reason == MARKET_NOT_READ


def test_a_resume_whose_market_could_not_be_read_says_why() -> None:
    market = PlannerMarket(None, None, None, None, "no book for BTCUSDT")

    (item,) = assess_resume(
        ResumeInputs(CONFIG, market, OwnerInventory(HELD, Decimal(500)), loaded())
    ).items

    assert item.code == "RUN_PLAN_UNREADABLE"
    assert item.reason == "The resumed ladder cannot be drawn: no book for BTCUSDT"
    assert item.fix is ReadinessFix.NONE


def test_a_resume_whose_parameters_cannot_be_read_is_named_not_passed() -> None:
    market = PlannerMarket(TERMS, grid_inputs().market, None, None)

    (item,) = assess_resume(
        ResumeInputs({}, market, OwnerInventory(HELD, Decimal(500)), loaded())
    ).items

    assert item.code == "RUN_PLAN_UNREADABLE"
    assert "parameters cannot be read" in item.reason


def test_a_plan_that_cannot_be_drawn_does_not_hide_the_snapshots_own_state() -> None:
    codes = [
        item.code
        for item in assess_resume(
            ResumeInputs(
                CONFIG, None, OwnerInventory(HELD, Decimal(500)), ExchangeChecking()
            )
        ).items
    ]

    assert codes == ["RUN_PLAN_READING", "RUN_EXCHANGE_CHECKING"]


def test_a_resume_at_the_click_is_refused_when_the_symbols_numbers_cannot_be_read(
    world: ReadinessWorld,
) -> None:
    """The planner numbers are read at the click; an unknown symbol has none."""
    stored = world.store.load(BotId(BOT))
    unknown = replace(stored.bot.definition, symbol="ZZZUSDT")
    world.store.save(StoredBot(replace(stored.bot, definition=unknown), stored.runtime))
    _hold(world, "4.132")
    runner = _Runner()

    result = _resume(world, runner)

    assert not result.accepted
    assert result.refusal is BotRefusal.VENUE_NOT_READY
    assert "The resumed ladder cannot be drawn" in result.message
    assert runner.resumed == []

"""`BOT-173` — readiness judged on the exchange's own facts, on the composed app.

@details The composed app over the fake Binance server. The snapshot is read from
the exchange (balances free and locked, the orders resting on the symbol, what an
earlier run kept); the Start and Resume use cases judge the same rules on facts read
at the click, so a click is refused for what the screen listed and nothing is placed.
No journey reaches a real exchange.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_readiness import (
    GetBotReadinessQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_exchange_facts import (
    ExchangeLoaded,
    ExchangeUnavailable,
    GetExchangeFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_STALE_AFTER_SECONDS,
)

from .grid_fake_exchange import (
    GRID,
    SPOT,
    SYMBOL,
    BootedApp,
    FakeExchange,
    booted,
    resting,
)
from .test_a_bot_owns_its_price_stream_on_the_fake_exchange import (
    _INSIDE_THE_RANGE,
    _publish_tick,
    _started,
)


def _snapshot(app: BootedApp, bot_id: str):
    return app.engine.dispatch(GetExchangeFactsQuery, GetExchangeFactsQuery(bot_id))


def _readiness(app: BootedApp, bot_id: str) -> BotReadiness:
    left = app.engine.dispatch(GetBotReadinessQuery, GetBotReadinessQuery(bot_id))
    assert isinstance(left, BotReadiness)
    return left


def _created(app: BootedApp, capital: str = "2000") -> str:
    created = app.engine.dispatch(
        CreateBotCommand,
        CreateBotCommand(
            "grid", "grid", SPOT, SYMBOL, {**GRID, "capital_quote": capital}
        ),
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None
    return created.bot_id


def _halted_by_a_silent_feed(app: BootedApp) -> str:
    bot_id = _started(app)
    _publish_tick(app, _INSIDE_THE_RANGE)
    app.monotonic.advance(PRICE_STALE_AFTER_SECONDS)
    app.ticker.fire()
    app.deliver()
    assert app.bot(bot_id).state is S.HALTED
    return bot_id


def test_the_snapshot_reads_the_balances_and_orders_the_exchange_reports(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)

        snapshot = _snapshot(app, bot_id)

        assert isinstance(snapshot, ExchangeLoaded)
        facts = snapshot.facts
        assert (facts.base_asset, facts.quote_asset) == ("BTC", "USDT")
        resting_orders = resting(app.urls)
        assert facts.own_open_orders == len(resting_orders)
        assert facts.foreign_open_orders == 0
        assert facts.own_open_orders > 0
        # The fake exchange keeps a resting order's funds free, as the
        # exchange's response says; the locked arithmetic is the unit tests'.
        assert facts.base_locked == facts.quote_locked == 0
        assert facts.base_free > 0 and facts.quote_free > 0


def test_a_stopped_bot_is_warned_before_start_of_the_base_its_run_kept(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)
        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, BaseHandling.KEEP)
        )
        assert isinstance(stopped, BotCommandResult) and stopped.accepted

        readiness = _readiness(app, bot_id)

        assert readiness.can_start, readiness.message()
        (advisory,) = readiness.advisories
        assert advisory.code == "EARLIER_RUNS_LEFT"
        assert advisory.text.startswith("A previous run kept ")
        assert " BTC ≈ " in advisory.text and advisory.text.endswith(
            "USDT that this run will not trade"
        )


def test_a_start_whose_quote_is_short_is_refused_with_both_numbers_and_places_nothing(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _created(app)
        spot = exchange.urls.spot_account
        spot.withdraw_free("USDT", spot.free_balance("USDT") - Decimal(1500))

        readiness = _readiness(app, bot_id)
        started = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))

        assert [item.code for item in readiness.items] == ["RUN_QUOTE_SHORT"]
        assert isinstance(started, BotCommandResult)
        assert started.refusal is BotRefusal.BALANCE_TOO_SMALL
        assert started.message == readiness.message()
        assert "Spot Testnet has 1500.00 USDT free" in started.message
        assert app.bot(bot_id).state is S.DRAFT
        assert resting(app.urls) == {}


def test_a_resume_whose_base_was_moved_by_hand_is_refused_before_any_order(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _halted_by_a_silent_feed(app)
        spot = exchange.urls.spot_account
        spot.withdraw_free("BTC", spot.free_balance("BTC") - Decimal("0.001"))

        resumed = app.engine.dispatch(ResumeBotCommand, ResumeBotCommand(bot_id))

        assert isinstance(resumed, BotCommandResult)
        assert resumed.refusal is BotRefusal.BALANCE_TOO_SMALL
        assert resumed.message.startswith(
            "Resume is blocked: The resumed ladder sells "
        )
        assert "BTC free" in resumed.message
        assert app.bot(bot_id).state is S.HALTED
        assert resting(app.urls) == {}


def test_a_resume_whose_base_is_all_there_is_queued(exchange: FakeExchange) -> None:
    with booted(exchange) as app:
        bot_id = _halted_by_a_silent_feed(app)

        resumed = app.engine.dispatch(ResumeBotCommand, ResumeBotCommand(bot_id))

        assert isinstance(resumed, BotCommandResult)
        assert resumed.accepted, resumed.message


def test_a_bot_that_is_not_there_is_an_unavailable_snapshot_naming_it(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        missing = app.engine.dispatch(
            GetExchangeFactsQuery, GetExchangeFactsQuery("nobody")
        )

        assert isinstance(missing, ExchangeUnavailable)
        assert "nobody" in missing.reason

"""`EPIC-034H` — the Start use case refuses exactly what the readiness query
reports, before any order and before anything is saved.

The screen shows the query's items before the click; Start asks the same
reader at the click. Each scenario below breaks one thing, then holds the
handler's refusal to the query's own words and to the refusal enum its first
item carries. The red-first proof is the mutation at the end: a handler that
skips the reader starts a bot the query says is not ready.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_readiness import (
    GetBotReadinessQuery,
    GetBotReadinessQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
    StartBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    add_bot,
    failing,
    readiness_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
    SYMBOL,
)


class _CountingRunner(IBotRunner):
    """Records the starts it is asked for; everything else is not used here."""

    def __init__(self) -> None:
        self.started: list[str] = []

    def start(self, bot_id: str) -> BotCommandResult:
        self.started.append(bot_id)
        return BotCommandResult.done(bot_id)

    def pause(self, bot_id: str) -> None:
        raise NotImplementedError

    def resume(self, bot_id: str) -> None:
        raise NotImplementedError

    def stop(self, bot_id: str, base: object) -> None:  # type: ignore[override]
        raise NotImplementedError

    def confirm_resume(self, bot_id: str) -> None:
        raise NotImplementedError

    def has_resume_proposal(self, bot_id: str) -> bool:
        return False


def _start(
    world: ReadinessWorld, runner: IBotRunner, config: dict[str, str] | None = None
) -> BotCommandResult:
    handler = StartBotCommandHandler(
        world.store, runner, BotCommandLock(), world.reader, world.clock
    )
    return handler.execute(StartBotCommand(BOT, config))


def _query(world: ReadinessWorld, config: dict[str, str] | None = None):
    return GetBotReadinessQueryHandler(world.store, world.reader).execute(
        GetBotReadinessQuery(BOT, config)
    )


def _unreachable(world: ReadinessWorld) -> None:
    failing(
        world,
        ConnectFailure(
            AccountSource.SPOT_TESTNET, ConnectionFailureKind.MAINTENANCE, "the account"
        ),
    )


def _another_bot_runs(world: ReadinessWorld) -> None:
    add_bot(world, "zzz999", S.RUNNING)


def _symbol_leased(world: ReadinessWorld) -> None:
    world.session.claim_symbol(SYMBOL, "strategy.1")


SCENARIOS = {
    "the account cannot be read": (_unreachable, BotRefusal.VENUE_NOT_READY),
    "another bot is running": (
        _another_bot_runs,
        BotRefusal.ONE_RUNNING_BOT_DURING_FAST_TRACK,
    ),
    "the symbol is leased": (_symbol_leased, BotRefusal.SYMBOL_LEASED),
}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_start_refuses_exactly_what_the_query_reports(scenario: str) -> None:
    world = readiness_world()
    breaking, refusal = SCENARIOS[scenario]
    breaking(world)
    runner = _CountingRunner()

    reported = _query(world)
    result = _start(world, runner)

    assert not reported.can_start
    assert result.refusal is refusal
    assert result.message == reported.message()
    assert runner.started == []


def test_a_ready_bot_is_reported_ready_and_started() -> None:
    world = readiness_world()
    runner = _CountingRunner()

    assert _query(world).can_start
    assert _start(world, runner).accepted
    assert runner.started == [BOT]


def test_a_capital_above_the_balance_is_refused_before_any_order() -> None:
    world = readiness_world(available=Decimal(999))
    runner = _CountingRunner()

    reported = _query(world)
    result = _start(world, runner)

    assert [i.code for i in reported.items] == ["CAPITAL_ABOVE_BALANCE"]
    assert result.refusal is BotRefusal.PARAMETERS_REFUSED
    assert "999" in result.message
    assert runner.started == []
    assert world.session.ready_requests == 0


_BELOW_THE_PRICE = {
    **CONFIG,
    "lower": "130",
    "upper": "160",
    "stop_loss": "price:120",
    "take_profit": "price:170",
}


def test_a_price_below_the_range_is_refused_and_the_screen_says_the_same() -> None:
    """`EPIC-035L`, D4 (a): the market is at 121 and the range starts at 130, so
    Start would market-buy the whole capital. The query the screen reads and the
    handler at the click give one answer, and no order goes out."""
    world = readiness_world(config=_BELOW_THE_PRICE)
    runner = _CountingRunner()

    reported = _query(world)
    result = _start(world, runner)

    assert [i.code for i in reported.items] == ["PRICE_BELOW_RANGE"]
    assert result.refusal is BotRefusal.PARAMETERS_REFUSED
    assert result.message == reported.message()
    assert "below the range's lower bound" in result.message
    assert runner.started == []


def test_a_price_above_the_range_warns_and_starts() -> None:
    above = {**CONFIG, "lower": "60", "upper": "100", "stop_loss": "price:50"}
    above["take_profit"] = "price:110"
    world = readiness_world(config=above)
    runner = _CountingRunner()

    assert _query(world).can_start
    assert _start(world, runner).accepted
    assert runner.started == [BOT]


def test_a_key_that_cannot_trade_is_refused() -> None:
    world = readiness_world(can_trade=False)

    result = _start(world, _CountingRunner())

    assert result.refusal is BotRefusal.PARAMETERS_REFUSED
    assert "cannot trade" in result.message


def test_a_per_order_cap_below_a_level_is_refused_by_the_planner() -> None:
    """250 USDT a level above a 200 cap: the planner's D21 refusal, now a
    design item the screen showed before the click."""
    world = readiness_world(cap=Decimal(200))

    result = _start(world, _CountingRunner())

    assert result.refusal is BotRefusal.PARAMETERS_REFUSED
    assert "cap" in result.message


def test_a_futures_venue_is_refused_in_the_venues_title() -> None:
    world = readiness_world(bot_venue=TradingVenue.FUTURES_TESTNET)
    # The fake serves the Spot source only, so a Futures bot's account is not
    # configured: Connect's item, in the venue's title.
    result = _start(world, _CountingRunner())

    assert result.refusal is BotRefusal.VENUE_NOT_READY
    assert "futures_testnet" not in result.message


def test_a_grid_count_past_trading_caps_is_a_budget_item() -> None:
    caps = replace(DEFAULT_OWNER_BUDGET_CAPS, max_open_orders=4)
    world = readiness_world(caps=caps)

    reported = _query(world)

    assert [i.code for i in reported.items] == ["RUN_BUDGET_REFUSED"]
    assert _start(world, _CountingRunner()).refusal is BotRefusal.BUDGET_REFUSED


def test_a_bot_that_is_not_there_is_one_item() -> None:
    world = readiness_world()
    world.store.delete(BotId(BOT))

    reported = _query(world)

    assert [i.code for i in reported.items] == ["RUN_NO_BOT"]
    assert _start(world, _CountingRunner()).refusal is BotRefusal.NOT_FOUND


# --- Save and Start (D8) -----------------------------------------------------


def test_save_and_start_judges_the_edits_saves_them_and_starts() -> None:
    world = readiness_world()
    edited = {**CONFIG, "capital_quote": "900"}
    runner = _CountingRunner()

    result = _start(world, runner, edited)

    assert result.accepted
    assert runner.started == [BOT]
    saved = world.store.load(BotId(BOT)).bot.definition.config
    assert saved["capital_quote"] == "900"


def test_save_and_start_with_edits_that_are_not_ready_saves_nothing() -> None:
    """The edits are judged as they would be saved, and refused before any
    write: a refused start never leaves them half-applied."""
    world = readiness_world(available=Decimal(500))
    edited = {**CONFIG, "capital_quote": "900"}
    runner = _CountingRunner()

    result = _start(world, runner, edited)

    assert result.refusal is BotRefusal.PARAMETERS_REFUSED
    assert runner.started == []
    assert world.store.load(BotId(BOT)).bot.definition.config == CONFIG


def test_save_and_start_with_the_saved_parameters_writes_nothing() -> None:
    world = readiness_world()
    before = world.store.load(BotId(BOT))

    _start(world, _CountingRunner(), dict(CONFIG))

    assert world.store.load(BotId(BOT)) == StoredBot(before.bot, before.runtime)


def test_the_query_judges_edits_that_are_not_saved_yet() -> None:
    world = readiness_world(available=Decimal(500))

    saved = _query(world)
    edited = _query(world, {**CONFIG, "capital_quote": "400"})

    assert "CAPITAL_ABOVE_BALANCE" in [i.code for i in saved.items]
    assert "CAPITAL_ABOVE_BALANCE" not in [i.code for i in edited.items]


def test_save_and_start_is_judged_on_the_edits_not_on_the_saved_parameters() -> None:
    """The saved 1,000 is above the 950 available; the edit to 900 fits. A
    start that judged what is saved would refuse what the screen showed ready."""
    world = readiness_world(available=Decimal(950))
    runner = _CountingRunner()

    assert not _query(world).can_start
    assert _query(world, {**CONFIG, "capital_quote": "900"}).can_start
    result = _start(world, runner, {**CONFIG, "capital_quote": "900"})

    assert result.accepted
    assert runner.started == [BOT]


def test_the_bots_own_lease_is_not_a_thing_left() -> None:
    """A bot that held its symbol before (a restart, a stop) is not blocked by
    its own claim."""
    world = readiness_world()
    world.session.claim_symbol(SYMBOL, f"bot.{BOT}")

    assert _query(world).can_start


class _RefusingRunner(_CountingRunner):
    """A runner whose own steps (the reconciliation, the budget) refuse."""

    def start(self, bot_id: str) -> BotCommandResult:
        super().start(bot_id)
        return BotCommandResult.refused(
            BotRefusal.VENUE_NOT_READY, "unexpected open positions", bot_id
        )


def test_a_refusal_the_runner_gives_leaves_the_edits_saved() -> None:
    """Save and start is save, then start: the list refuses before the write,
    the runner's own refusals come after it."""
    world = readiness_world()
    edited = {**CONFIG, "capital_quote": "900"}

    result = _start(world, _RefusingRunner(), edited)

    assert result.refusal is BotRefusal.VENUE_NOT_READY
    assert world.store.load(BotId(BOT)).bot.definition.config["capital_quote"] == "900"


# --- the mainnet venues (`EPIC-034` D11) --------------------------------------

_SPOT_VENUES = (TradingVenue.SPOT_TESTNET, TradingVenue.SPOT_MAINNET)


@pytest.mark.parametrize("venue", _SPOT_VENUES)
def test_a_ready_spot_bot_starts_on_every_spot_venue_the_same_way(
    venue: TradingVenue,
) -> None:
    """Mainnet is the same readiness as testnet, read from its own account."""
    world = readiness_world(venue=venue)
    runner = _CountingRunner()

    assert _query(world).can_start
    assert _start(world, runner).accepted
    assert runner.started == [BOT]


def test_a_mainnet_key_the_gate_refused_stops_start_and_names_the_venue() -> None:
    """The key gate (`EPIC-034` D5) answers through the account read, so a key
    that can withdraw is a Connect item that Start refuses on, before any order."""
    world = readiness_world(venue=TradingVenue.SPOT_MAINNET)
    failing(
        world,
        ConnectFailure(
            AccountSource.SPOT_MAINNET,
            ConnectionFailureKind.WITHDRAWAL_ENABLED,
            "withdrawals",
        ),
    )
    runner = _CountingRunner()

    reported = _query(world)
    result = _start(world, runner)

    assert not reported.can_start
    assert [i.code for i in reported.items] == ["CONNECT_FAILED"]
    assert "Spot Mainnet" in reported.items[0].reason
    assert result.refusal is BotRefusal.VENUE_NOT_READY
    assert runner.started == []

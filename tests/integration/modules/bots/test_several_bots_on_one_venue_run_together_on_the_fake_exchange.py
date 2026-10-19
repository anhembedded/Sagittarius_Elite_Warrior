"""`EPIC-029J` J1b - bots on different symbols of one venue run together in one composed app.

@details Real everything but the network and the websocket (`two_venues_bots_world`). Each test
states one promise of the slice: several bots of one venue start and each holds only its own
orders; a second bot on a symbol that is taken is refused naming its holder; a venue at the cap
refuses the next bot; a fill and its profit reach only the bot whose tag it carries; stopping one
leaves the others resting; an Emergency Stop halts every bot of its venue and none of the other.
"""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.executor_bindings import (
    grid_executor_deps,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.venue_bot_cap import (
    MAX_ACTIVE_BOTS_PER_VENUE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)

from .crowd_bots_world import (
    ETH_GRID,
    ETH_SPOT_GRID,
    FUTURES_SYMBOLS,
    create_bot,
    run_bots,
    start_bot,
)
from .grid_fake_exchange import FakeExchange, ladder
from .two_venues_bots_world import FUTURES, SPOT, SYMBOL, booted_two_venues

S = BotLifecycleState
#: Three symbols of Futures Testnet that trade at the one mark, so the one grid fits each.
THREE = FUTURES_SYMBOLS[:3]


def test_bots_on_three_symbols_of_one_venue_run_together_each_with_its_own_orders(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        bots = run_bots(app, FUTURES, THREE)

        for symbol, bot_id in bots.items():
            assert app.bot(bot_id).state is S.RUNNING
            resting = app.resting(FUTURES, symbol)
            assert resting == set(ladder(app.runtime(bot_id)))
            assert resting
            assert {tag_of(oid) for oid in resting} == {bot_id}


def test_a_btc_bot_and_an_eth_bot_run_together_on_futures_testnet(
    both_venues: FakeExchange,
) -> None:
    """The owner's desktop: two symbols of one venue, each at its own price."""
    with booted_two_venues(both_venues) as app:
        btc = create_bot(app, FUTURES, "BTCUSDT")
        eth = create_bot(app, FUTURES, "ETHUSDT", params=ETH_GRID)
        for bot_id in (btc, eth):
            started = start_bot(app, bot_id)
            assert started.accepted, started.message

        assert (app.bot(btc).state, app.bot(eth).state) == (S.RUNNING, S.RUNNING)
        assert {tag_of(o) for o in app.resting(FUTURES, "BTCUSDT")} == {btc}
        assert {tag_of(o) for o in app.resting(FUTURES, "ETHUSDT")} == {eth}
        assert app.resting(FUTURES, "ETHUSDT") == set(ladder(app.runtime(eth)))


def test_a_second_bot_on_a_symbol_that_is_taken_is_refused_naming_its_holder(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        bots = run_bots(app, FUTURES, THREE)
        another = create_bot(app, FUTURES, THREE[1], "second eth")

        refused = start_bot(app, another)

        assert refused.refusal is BotRefusal.ONE_ACTIVE_BOT_PER_SYMBOL
        assert (
            f"A bot on Futures Testnet is still active on {THREE[1]} ({bots[THREE[1]]})"
            in refused.message
        )
        assert app.bot(another).state is S.DRAFT
        assert app.resting(FUTURES, THREE[1]) == set(
            ladder(app.runtime(bots[THREE[1]]))
        )


def test_a_symbol_leased_to_someone_else_is_refused_naming_the_lessee(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        app.scopes[FUTURES].session_state.claim_symbol(THREE[2], "strategy.x")
        bot_id = create_bot(app, FUTURES, THREE[2])

        refused = start_bot(app, bot_id)

        assert refused.refusal is BotRefusal.SYMBOL_LEASED
        assert f"{THREE[2]} is held by strategy.x" in refused.message
        assert app.bot(bot_id).state is S.DRAFT


def test_a_venue_at_the_cap_refuses_the_next_bot_and_frees_a_place_when_one_stops(
    both_venues: FakeExchange, weight_gate_lifted: None
) -> None:
    with booted_two_venues(both_venues) as app:
        bots = run_bots(app, FUTURES, FUTURES_SYMBOLS[:MAX_ACTIVE_BOTS_PER_VENUE])
        next_symbol = FUTURES_SYMBOLS[MAX_ACTIVE_BOTS_PER_VENUE]
        over = create_bot(app, FUTURES, next_symbol)

        refused = start_bot(app, over)

        assert refused.refusal is BotRefusal.VENUE_FULL
        for bot_id in bots.values():
            assert bot_id in refused.message
        assert app.bot(over).state is S.DRAFT
        # another venue is a venue of its own: the Spot Testnet takes a bot beside them
        assert start_bot(app, create_bot(app, SPOT, SYMBOL)).accepted

        first = next(iter(bots.values()))
        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(first, ExposureHandling.CLOSE_AT_MARKET)
        )
        assert isinstance(stopped, BotCommandResult)
        assert stopped.accepted, stopped.message
        assert start_bot(app, over).accepted


def test_a_fill_and_its_profit_reach_only_the_bot_whose_tag_it_carries(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        bots = run_bots(app, FUTURES, THREE)
        before = {symbol: app.runtime(bot_id) for symbol, bot_id in bots.items()}

        app.move_price(
            FUTURES, 62900, THREE[1]
        )  # the 63,000 buy fills on the second symbol

        after = {symbol: app.runtime(bot_id) for symbol, bot_id in bots.items()}
        assert after[THREE[1]].inventory > before[THREE[1]].inventory
        assert after[THREE[0]] == before[THREE[0]]
        assert after[THREE[2]] == before[THREE[2]]
        for symbol, bot_id in bots.items():
            assert app.resting(FUTURES, symbol) == set(ladder(app.runtime(bot_id)))


def test_stopping_one_bot_leaves_the_others_of_the_venue_resting(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        bots = run_bots(app, FUTURES, THREE)

        stopped = app.engine.dispatch(
            StopBotCommand,
            StopBotCommand(bots[THREE[0]], ExposureHandling.CLOSE_AT_MARKET),
        )
        assert isinstance(stopped, BotCommandResult)
        assert stopped.accepted, stopped.message

        assert app.bot(bots[THREE[0]]).state is S.STOPPED
        assert app.resting(FUTURES, THREE[0]) == set()
        for symbol in THREE[1:]:
            assert app.bot(bots[symbol]).state is S.RUNNING
            assert app.resting(FUTURES, symbol) == set(
                ladder(app.runtime(bots[symbol]))
            )


def test_an_emergency_stop_halts_every_bot_of_its_venue_and_none_of_the_other(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        futures_bots = run_bots(app, FUTURES, THREE)
        spot = run_bots(app, SPOT, (SYMBOL,))[SYMBOL]
        spot_ladder = app.resting(SPOT)

        app.engine.dispatch(EmergencyStopCommand, EmergencyStopCommand(venue=FUTURES))
        app.deliver()

        for symbol, bot_id in futures_bots.items():
            assert app.bot(bot_id).state is S.HALTED
            assert app.runtime(bot_id).reason is GridReason.SWITCH_OFF
            assert app.resting(FUTURES, symbol) == set()
        assert app.scopes[FUTURES].session_state.enabled is False
        assert app.bot(spot).state is S.RUNNING
        assert app.scopes[SPOT].session_state.enabled is True
        assert app.resting(SPOT) == spot_ladder == set(ladder(app.runtime(spot)))


def test_a_bot_waiting_to_recover_holds_back_a_start_on_its_venue_until_it_is_resumed(
    both_venues: FakeExchange,
) -> None:
    """`EPIC-042E`'s latent risk, closed for Start: a Start opens the venue's order session, and
    the session's opening reconciles every RECOVERING bot of the venue. After a restart, starting
    a bot on another symbol would put the first one back to trading without the owner's resume."""
    with booted_two_venues(both_venues) as first:
        waiting = run_bots(first, SPOT, (SYMBOL,))[SYMBOL]

    with booted_two_venues(both_venues, open_sessions=False) as second:
        assert second.bot(waiting).state is S.RECOVERING
        other = create_bot(second, SPOT, "ETHUSDT", params=ETH_SPOT_GRID)

        refused = start_bot(second, other)

        assert refused.refusal is BotRefusal.VENUE_RECOVERING
        assert waiting in refused.message
        assert second.bot(other).state is S.DRAFT
        assert second.bot(waiting).state is S.RECOVERING, "the Start resumed nobody"

        resumed = second.engine.dispatch(
            ResumeBotCommand, ResumeBotCommand(waiting, real_money_confirmed=True)
        )
        assert isinstance(resumed, BotCommandResult)
        assert resumed.accepted, resumed.message
        assert second.bot(waiting).state is S.RUNNING
        assert start_bot(second, other).accepted


def test_resuming_one_recovering_bot_leaves_the_other_recovering_bot_of_the_venue_waiting(
    both_venues: FakeExchange,
) -> None:
    """`BOT-183`: a Resume opens the venue's order session, and the opening used to reconcile
    every RECOVERING bot of the venue, so a bot the owner did not resume traded again. The opening
    is now announced as the resumed bot's: the other waits for its own Resume (ADR 038 O2)."""
    with booted_two_venues(both_venues) as first:
        resumed = run_bots(first, SPOT, (SYMBOL,))[SYMBOL]
        waiting = create_bot(first, SPOT, "ETHUSDT", params=ETH_SPOT_GRID)
        assert start_bot(first, waiting).accepted

    with booted_two_venues(both_venues, open_sessions=False) as second:
        assert second.bot(resumed).state is S.RECOVERING
        assert second.bot(waiting).state is S.RECOVERING

        answer = second.engine.dispatch(
            ResumeBotCommand, ResumeBotCommand(resumed, real_money_confirmed=True)
        )
        second.deliver()

        assert isinstance(answer, BotCommandResult)
        assert answer.accepted, answer.message
        assert second.bot(resumed).state is S.RUNNING
        assert second.bot(waiting).state is S.RECOVERING, "another bot's Resume woke it"

        own = second.engine.dispatch(
            ResumeBotCommand, ResumeBotCommand(waiting, real_money_confirmed=True)
        )
        assert isinstance(own, BotCommandResult)
        assert own.accepted, own.message
        assert second.bot(waiting).state is S.RUNNING


def test_the_production_wiring_gives_the_bots_of_a_venue_one_pacer(
    both_venues: FakeExchange,
) -> None:
    """The worlds above inject their own pacer; this is the default graph `create_app()` builds."""
    with booted_two_venues(both_venues) as app:
        deps = grid_executor_deps(app.engine.container)
        spacing = timedelta(milliseconds=250)

        assert deps.pacers(FUTURES, spacing) is deps.pacers(FUTURES, spacing)
        assert deps.pacers(FUTURES, spacing) is not deps.pacers(SPOT, spacing)

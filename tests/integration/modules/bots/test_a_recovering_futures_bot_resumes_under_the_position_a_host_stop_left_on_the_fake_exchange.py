"""A Futures bot a host stop left under its protective stop can be resumed after the restart.

@details The owner's VPS (Futures Testnet): `--on-stop leave-orders` leaves a bot whose stop covers
its position (`EPIC-038M`, O12), the restart brings it back RECOVERING with the order session
closed, and the only way out is the bot's own Resume (decision O2). Resume opens the session, and
the session refused every position on the account, the bots' own included ("The account has
unexpected open positions"), so a bot could be neither resumed nor stopped. The composed app, two
Futures bots on two symbols as on the VPS, a real restart with the session closed; nothing but the
network and the websocket is substituted.

The position of a bot is excused only by the exchange's own evidence (its tagged order and trade
history), never by the bot's file, and only for a resume or stop of a venue's own bot: a position
nobody's history explains, or more than the tagged history explains, still refuses.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StopBotForOperatorCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType

from .crowd_bots_world import ETH_GRID, FUTURES_SYMBOLS, create_bot, start_bot
from .grid_fake_exchange import FakeExchange, ladder
from .two_venues_bots_world import (
    FUTURES,
    SPOT,
    SYMBOL,
    BootedTwoVenues,
    booted_two_venues,
)

S = BotLifecycleState
D = Decimal
ETH = "ETHUSDT"
THIRD = FUTURES_SYMBOLS[2]
#: What the user's own click on the exchange's website adds: far beyond one quantity step.
BY_HAND = D("0.5")


def _position(app: BootedTwoVenues, symbol: str) -> Decimal:
    return sum(
        (p.position_amt for p in app.client(FUTURES).get_positions(symbol)), D(0)
    )


def _by_hand(app: BootedTwoVenues, symbol: str, quantity: Decimal) -> None:
    """A market buy nobody here sent."""
    app.client(FUTURES).place_order(
        Order(
            client_order_id=ClientOrderId("web-by-hand"),
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=quantity,
        )
    )


class _Heard(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@contextmanager
def _heard() -> Iterator[list[str]]:
    """What the session said (the composed app turns propagation off, so `caplog` hears nothing)."""
    handler = _Heard()
    logger = logging.getLogger("App.TradingSession")
    logger.addHandler(handler)
    try:
        yield handler.lines
    finally:
        logger.removeHandler(handler)


def _resume(app: BootedTwoVenues, bot_id: str) -> BotCommandResult:
    answer = app.engine.dispatch(
        ResumeBotCommand, ResumeBotCommand(bot_id, real_money_confirmed=True)
    )
    assert isinstance(answer, BotCommandResult)
    return answer


@contextmanager
def _restarted_with_two_bots_left(
    both_venues: FakeExchange,
) -> Iterator[tuple[BootedTwoVenues, str, str]]:
    """The VPS: two Futures bots running, the host stops leaving them, the app starts again."""
    with booted_two_venues(both_venues) as first:
        btc = create_bot(first, FUTURES, SYMBOL)
        eth = create_bot(first, FUTURES, ETH, params=ETH_GRID)
        for bot_id in (btc, eth):
            started = start_bot(first, bot_id)
            assert started.accepted, started.message
        assert _position(first, SYMBOL) > 0 and _position(first, ETH) > 0

    with booted_two_venues(both_venues, open_sessions=False) as second:
        second.futures_stream.start = lambda: None  # type: ignore[method-assign]
        assert second.scopes[FUTURES].session_state.enabled is False
        assert (second.bot(btc).state, second.bot(eth).state) == (
            S.RECOVERING,
            S.RECOVERING,
        )
        yield second, btc, eth


def test_a_recovering_bot_resumes_and_adopts_its_ladder_and_its_position(
    both_venues: FakeExchange,
) -> None:
    with _restarted_with_two_bots_left(both_venues) as (app, btc, eth):
        held = {SYMBOL: _position(app, SYMBOL), ETH: _position(app, ETH)}

        with _heard() as lines:
            answer = _resume(app, btc)

        assert answer.accepted, answer.message
        assert app.scopes[FUTURES].session_state.enabled is True
        assert app.bot(btc).state is S.RUNNING
        assert app.runtime(btc).inventory == held[SYMBOL] == _position(app, SYMBOL)
        assert app.resting(FUTURES, SYMBOL) == set(ladder(app.runtime(btc)))
        assert _position(app, ETH) == held[ETH], (
            "the other bot's position was not touched"
        )
        assert app.bot(eth).state is S.RECOVERING, "another bot's Resume woke it"
        excused = [
            line for line in lines if "excused" in line and "[position-claim]" in line
        ]
        assert {symbol in " ".join(excused) for symbol in (SYMBOL, ETH)} == {True}, (
            lines
        )

        own = _resume(app, eth)

        assert own.accepted, own.message
        assert app.bot(eth).state is S.RUNNING
        assert app.runtime(eth).inventory == held[ETH]


def test_the_operators_stop_of_a_recovering_bot_closes_its_position_through_the_same_opening(
    both_venues: FakeExchange,
) -> None:
    """`bot stop --close-position` opens the closed session as a Resume does, and met the same
    refusal over the bot's own position."""
    with _restarted_with_two_bots_left(both_venues) as (app, btc, eth):
        answer = app.engine.dispatch(
            StopBotForOperatorCommand,
            StopBotForOperatorCommand(
                btc, confirmed_venue=FUTURES.value, close_position=True
            ),
        )
        app.deliver()

        assert isinstance(answer, BotCommandResult)
        assert answer.accepted, answer.message
        assert app.bot(btc).state is S.STOPPED
        assert _position(app, SYMBOL) == 0 and app.resting(FUTURES, SYMBOL) == set()
        assert _position(app, ETH) > 0, "the other bot's position was not touched"
        assert app.bot(eth).state is S.RECOVERING


def test_a_position_no_bots_history_explains_still_refuses_the_resume(
    both_venues: FakeExchange,
) -> None:
    with _restarted_with_two_bots_left(both_venues) as (app, btc, eth):
        _by_hand(app, THIRD, D("0.5"))

        answer = _resume(app, btc)

        assert answer.refusal is BotRefusal.VENUE_NOT_READY
        assert "unexpected open positions" in answer.message
        assert f"{THIRD} holds 0.5" in answer.message
        assert "and no bot of this venue claims it" in answer.message
        assert app.scopes[FUTURES].session_state.enabled is False
        assert app.bot(btc).state is S.RECOVERING and app.bot(eth).state is S.RECOVERING


def test_more_than_the_bots_own_history_explains_on_its_symbol_still_refuses_the_resume(
    both_venues: FakeExchange,
) -> None:
    with _restarted_with_two_bots_left(both_venues) as (app, btc, _eth):
        own = _position(app, SYMBOL)
        _by_hand(app, SYMBOL, BY_HAND)
        assert _position(app, SYMBOL) == own + BY_HAND

        answer = _resume(app, btc)

        assert answer.refusal is BotRefusal.VENUE_NOT_READY
        assert "unexpected open positions" in answer.message
        assert SYMBOL in answer.message and str(own + BY_HAND) in answer.message
        assert app.scopes[FUTURES].session_state.enabled is False
        assert app.bot(btc).state is S.RECOVERING


def test_a_start_still_refuses_while_a_position_stands_that_it_does_not_own(
    both_venues: FakeExchange,
) -> None:
    """Only a bot acting on its own run excuses its position: a Start of another bot passes no
    claim, so the account's positions still refuse it."""
    with _restarted_with_two_bots_left(both_venues) as (app, btc, _eth):
        other = create_bot(app, FUTURES, THIRD)

        refused = app.engine.dispatch(
            StartBotCommand, StartBotCommand(other, real_money_confirmed=True)
        )

        assert isinstance(refused, BotCommandResult)
        assert not refused.accepted
        assert app.scopes[FUTURES].session_state.enabled is False
        assert app.bot(btc).state is S.RECOVERING


def test_spot_is_unaffected(both_venues: FakeExchange) -> None:
    """Spot has no positions: a restart's Spot bot resumes as before."""
    with booted_two_venues(both_venues) as first:
        spot = create_bot(first, SPOT, SYMBOL)
        assert start_bot(first, spot).accepted

    with booted_two_venues(both_venues, open_sessions=False) as second:
        second.spot_stream.start = lambda: None  # type: ignore[method-assign]
        assert second.bot(spot).state is S.RECOVERING

        answer = _resume(second, spot)

        assert answer.accepted, answer.message
        assert second.bot(spot).state is S.RUNNING

"""`BUG-274` - the Bots screen's Stop on a bot waiting for a closed order session opens it and finishes.

@details The owner's desktop: a HALTED Futures bot, the app started again (a start always leaves the
venue's order session closed), Stop pressed twice. The bot went HALTED -> STOPPING and stayed there:
`StopBotCommandHandler` never opened the session, the stop's budget registration was refused with
"the order session is not open", and nothing cancelled or closed. Resume, Start and the headless
`bot stop` open the session; the screen's Stop did not. The same mechanism holds a RECOVERING bot,
which this journey uses (a real restart over the fake Futures exchange, the session closed).

The command is built by the screen's own `command_for`, so the test fails if the screen stops
carrying the person's answer; an automated Stop (the loss cap, the host's shutdown policy) carries
none and still opens nothing: a late order must not undo an Emergency Stop.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_progress_reader import (
    bot_progress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_commands import (
    command_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType

from .crowd_bots_world import create_bot, start_bot
from .grid_fake_exchange import FakeExchange
from .test_a_recovering_futures_bot_resumes_under_the_position_a_host_stop_left_on_the_fake_exchange import (
    ETH,
    FUTURES,
    SYMBOL,
    BootedTwoVenues,
    _position,
    _restarted_with_two_bots_left,
)
from .two_venues_bots_world import booted_two_venues

S = BotLifecycleState
D = Decimal


def _screen_stop(app: BootedTwoVenues, bot_id: str) -> BotCommandResult:
    """The click: the screen's dialogs answer "close the position", the real-money question yes."""
    dialogs = BotsDialogs(
        ask_new_bot=lambda _kinds, _venues: None,
        ask_stop=lambda _bot: ExposureHandling.CLOSE_AT_MARKET,
        confirm_delete=lambda _bot: False,
        ask_arm_strategy=lambda _question: None,
        choose_venue=lambda _choice: None,
        allow_real_money=lambda _venue, _what: True,
        ask_export_plan=lambda _bots, _selected: None,
        ask_plan_save_path=lambda _suggested: "",
    )
    stored = app.store.load(BotId(bot_id))
    snapshot = BotSnapshot.of(stored.bot, bot_progress(stored))
    command = command_for(BotAction.STOP, snapshot, dialogs)
    assert isinstance(command, StopBotCommand)
    answer = app.engine.dispatch(StopBotCommand, command)
    app.deliver()
    assert isinstance(answer, BotCommandResult)
    return answer


def test_the_screens_stop_opens_the_closed_session_and_the_bot_reaches_stopped(
    both_venues: FakeExchange,
) -> None:
    with _restarted_with_two_bots_left(both_venues) as (app, btc, eth):
        assert app.scopes[FUTURES].session_state.enabled is False

        answer = _screen_stop(app, btc)

        assert answer.accepted, answer.message
        assert app.scopes[FUTURES].session_state.enabled is True
        assert app.bot(btc).state is S.STOPPED, app.runtime(btc).reason_detail
        assert _position(app, SYMBOL) == 0 and app.resting(FUTURES, SYMBOL) == set()
        assert _position(app, ETH) > 0, "the other bot's position was not touched"
        assert app.bot(eth).state is S.RECOVERING, "another bot's Stop woke it"


def test_an_automated_stop_opens_no_session_and_waits_saying_how_to_open_it(
    both_venues: FakeExchange,
) -> None:
    """The loss cap and the host's shutdown policy dispatch `StopBotCommand` with no answer of a
    person's: a closed session stays closed (a late order must not undo an Emergency Stop), and the
    bot waits in STOPPING saying so."""
    with _restarted_with_two_bots_left(both_venues) as (app, btc, _eth):
        answer = app.engine.dispatch(
            StopBotCommand, StopBotCommand(btc, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        assert isinstance(answer, BotCommandResult)
        assert answer.accepted, answer.message
        assert app.scopes[FUTURES].session_state.enabled is False
        assert app.bot(btc).state is S.STOPPING
        assert "the order session is not open" in app.runtime(btc).reason_detail
        assert "press Stop" in app.runtime(btc).reason_detail


@contextmanager
def _restarted_after_a_fill_while_down(
    both_venues: FakeExchange,
) -> Iterator[tuple[BootedTwoVenues, str]]:
    """One Futures bot running; the app closes; the 62,900 buy fills on the way down, so its
    counter order is owed; the app starts again with the session closed (RECOVERING)."""
    with booted_two_venues(both_venues) as first:
        bot_id = create_bot(first, FUTURES, SYMBOL)
        assert start_bot(first, bot_id).accepted
    book = both_venues.urls.futures_book
    book.move_price(SYMBOL, D(62900))
    book.drain_user_data_events()
    with booted_two_venues(both_venues, open_sessions=False) as second:
        second.futures_stream.start = lambda: None  # type: ignore[method-assign]
        assert second.bot(bot_id).state is S.RECOVERING
        yield second, bot_id


def test_the_stop_lays_no_new_ladder_order_before_it_takes_the_ladder_off(
    both_venues: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Opening the session for a RECOVERING bot must not wake it: its reconcile would lay the
    counter order it owes (a new real-money order) ahead of the Stop already queued behind it."""
    real = FuturesTradingClient.place_order
    sent: list[Order] = []

    def place_order(self: FuturesTradingClient, order: Order) -> Order:
        sent.append(order)
        return real(self, order)

    with _restarted_after_a_fill_while_down(both_venues) as (app, bot_id):
        monkeypatch.setattr(FuturesTradingClient, "place_order", place_order)

        answer = _screen_stop(app, bot_id)

        assert answer.accepted, answer.message
        assert app.bot(bot_id).state is S.STOPPED
        laid = [order for order in sent if order.order_type is OrderType.LIMIT]
        assert laid == [], f"the Stop laid {len(laid)} new ladder order(s) first"
        # The buy that filled while the app was closed is booked at its cost: the price fell below
        # every entry, so the stopped run reports a loss, not the fill's whole proceeds as profit.
        assert app.runtime(bot_id).realised_total < 0

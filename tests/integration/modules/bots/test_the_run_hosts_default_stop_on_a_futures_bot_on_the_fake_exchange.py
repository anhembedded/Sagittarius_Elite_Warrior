"""`EPIC-038M` (decision O12) - the host's default stop on a Futures bot, on the fake Futures exchange.

@details The composed app with a real Futures Grid (`futures_bots_world`): the production executor,
the production protection and the fake's `closePosition` semantics. `LeaveOrdersResting` is run as
the host runs it on `systemctl stop`:

  · a bot whose position stands under its protective stop is left exactly as it is - the position,
    the ladder and the stop stay, and the server saw no order placed or cancelled;
  · a bot whose stop is gone (cancelled by hand), or whose stop cannot be read, is closed through
    the Stop the Bots tab uses - the ladder cancelled, the position closed at market - and ends flat.

Nothing here reaches a real exchange.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_account_reads import (
    BotAccountReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.leave_orders_resting import (
    LeaveOrdersResting,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_policy import (
    StopLedger,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.unconfirmed_orders import (
    closing_order_for,
)

from .futures_bots_world import BootedFuturesBots, booted_futures_bots
from .futures_direction_scenarios import NEUTRAL
from .futures_fake_exchange import SYMBOL
from .futures_stop_helpers import started, stops
from .grid_fake_exchange import FakeExchange

S = BotLifecycleState
D = Decimal
_LOGGER = "App.Operations.StopPolicy"
_PLACING_OR_CANCELLING = ("POST", "PUT", "DELETE")


class _Messages(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.lines: list[tuple[int, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append((record.levelno, record.getMessage()))


@contextmanager
def _heard() -> Iterator[list[tuple[int, str]]]:
    """What the policy said (the composed app turns propagation off, so `caplog` hears nothing)."""
    handler = _Messages()
    logger = logging.getLogger(_LOGGER)
    logger.addHandler(handler)
    try:
        yield handler.lines
    finally:
        logger.removeHandler(handler)


def _dispatcher(app: BootedFuturesBots) -> ICommandDispatcher:
    return app.engine.container.resolve(ICommandDispatcher)  # type: ignore[type-abstract, no-any-return]


def _host_stops(app: BootedFuturesBots, ledger: StopLedger) -> None:
    """The host's default policy, as `run` builds it, with the whole stop timeout it has."""
    LeaveOrdersResting(_dispatcher(app), 25.0, poll_s=0).apply(
        ledger, threading.Event()
    )
    app.deliver()


def test_a_bot_whose_position_stands_under_its_stop_is_left_as_it_is(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        position = app.position()
        ladder = app.resting()
        (stop,) = stops(app)
        assert position > 0 and ladder
        requests = len(app.exchange.urls.requests)
        ledger = StopLedger()

        with _heard() as lines:
            _host_stops(app, ledger)

        asked = app.exchange.urls.requests[requests:]
        assert not [r for r in asked if r[0] in _PLACING_OR_CANCELLING], asked
        assert app.position() == position
        assert app.resting() == ladder
        assert stops(app) == [stop]
        assert app.bot(bot_id).state is S.RUNNING
        assert ledger.left() == () and ledger.finished() == ()
        assert not [text for level, text in lines if level >= logging.WARNING]
        assert any("its stop covers its position" in text for _, text in lines)


def test_a_bot_whose_stop_was_cancelled_by_hand_is_closed_flat_before_exit(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        assert app.position() > 0
        # Cancelled from the exchange's own screen: the bot's record still says it stands.
        futures.urls.futures_book.algo.cancel_all(SYMBOL)
        assert stops(app) == []
        ledger = StopLedger()

        with _heard() as lines:
            _host_stops(app, ledger)

        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        assert app.resting() == {}
        assert stops(app) == []
        assert ledger.finished() == (bot_id,) and ledger.left() == ()
        warnings = [text for level, text in lines if level >= logging.WARNING]
        assert any(
            bot_id in text and "not on the exchange" in text for text in warnings
        )


def test_a_bot_whose_stop_cannot_be_read_is_closed_not_left(
    futures: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unread stop is not a covering stop: the stop stands, but the host cannot tell."""
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        real = BotAccountReads.protective_orders
        unreadable = {"on": True}

        def read(self: BotAccountReads) -> object:
            if unreadable["on"]:
                raise ConnectionError("the exchange could not be reached")
            return real(self)

        monkeypatch.setattr(BotAccountReads, "protective_orders", read)
        ledger = StopLedger()

        with _heard() as lines:
            # The read fails while the host asks; the Stop's own work then reads again.
            LeaveOrdersResting(_dispatcher(app), 25.0, poll_s=0).apply(
                ledger, _Released(unreadable)
            )
            app.deliver()

        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        warnings = [text for level, text in lines if level >= logging.WARNING]
        assert any(bot_id in text and "could not be read" in text for text in warnings)


def _flattened_by_hand(app: BootedFuturesBots) -> None:
    """The account's position closed from the exchange's own screen: the bot has not heard of it."""
    for position in app.client().get_positions(SYMBOL):
        app.client().place_order(closing_order_for(position))
    assert app.position() == 0


def test_a_flat_bot_whose_ladder_still_rests_is_closed_because_a_fill_would_open_a_position(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        _flattened_by_hand(app)
        assert app.resting(), "the ladder rests over a flat account"
        ledger = StopLedger()

        with _heard() as lines:
            _host_stops(app, ledger)

        assert app.bot(bot_id).state is S.STOPPED
        assert app.resting() == {} and app.position() == 0
        warnings = [text for level, text in lines if level >= logging.WARNING]
        assert any(bot_id in text and "ladder order" in text for text in warnings)


def test_a_flat_bot_with_nothing_resting_is_left(futures: FakeExchange) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        _flattened_by_hand(app)
        app.client().cancel_regular_orders(SYMBOL)
        futures.urls.futures_book.algo.cancel_all(SYMBOL)
        assert app.resting() == {} and stops(app) == []
        requests = len(app.exchange.urls.requests)
        ledger = StopLedger()

        with _heard() as lines:
            # Not `_host_stops`: its `deliver` would hand the bot the events of the flattening.
            LeaveOrdersResting(_dispatcher(app), 25.0, poll_s=0).apply(
                ledger, threading.Event()
            )

        asked = app.exchange.urls.requests[requests:]
        assert not [r for r in asked if r[0] in _PLACING_OR_CANCELLING], asked
        assert app.bot(bot_id).state is S.RUNNING and ledger.left() == ()
        assert not [text for level, text in lines if level >= logging.WARNING]
        assert any("rests no ladder" in text for _, text in lines)


def test_a_neutral_bot_long_under_its_one_stop_is_closed_because_its_ladder_can_flip_it(
    futures: FakeExchange,
) -> None:
    """Review of #626, finding 3: a NEUTRAL grid stands the stop of the covering side only, and the
    SELL ladder above can fill through zero and open a short that no stop covers."""
    with booted_futures_bots(futures) as app:
        bot_id = started(app, NEUTRAL.config)
        app.move_price(D(62900))
        assert app.position() > 0, "a BUY filled: the bot is long"
        app.ticker.fire()  # the price watch's beat places the stop over the new position
        (stop,) = stops(app)
        assert stop["side"] == "SELL", "the one stop that covers a long"
        assert app.resting(), "the SELL ladder above still rests"
        ledger = StopLedger()

        with _heard() as lines:
            _host_stops(app, ledger)

        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0 and app.resting() == {}
        warnings = [text for level, text in lines if level >= logging.WARNING]
        assert any(bot_id in text and "NEUTRAL" in text for text in warnings)


class _Released(threading.Event):
    """A `give_up` that is never set; it lets the exchange be readable again once the host has asked."""

    def __init__(self, unreadable: dict[str, bool]) -> None:
        super().__init__()
        self._unreadable = unreadable

    def wait(self, timeout: float | None = None) -> bool:
        self._unreadable["on"] = False
        return super().wait(timeout)

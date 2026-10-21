"""`BOT-184` — the bots of a venue read its positions once between them, and never judge on a
reading older than half a beat or older than the last order this app sent.

`VenuePositionReads` is the one reading; `BotOrderGateway` drops it when an order is sent or
cancelled and serves a bot's idle watches from it (`watched_position`), while a confirmation
(`position`) always asks the account."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    BotIdentity,
    BotOrderGateway,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_shared_reads import (
    BotSharedReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.shared_position_reads import (
    SHARED_READING_MAX_AGE_SECONDS,
    SharedPositionReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.venue_position_reads import (
    VenuePositionReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.bot_price_watch import (
    CHECK_EVERY_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_monotonic_clock import (
    FakeMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_AT = datetime(2026, 10, 21, tzinfo=UTC)


def _position(symbol: str, amount: str) -> LivePosition:
    return LivePosition(
        symbol=symbol,
        position_amt=Decimal(amount),
        entry_price=Decimal(100),
        mark_price=Decimal(100),
        unrealized_pnl=Decimal(0),
        leverage=3,
        margin_type=MarginType.ISOLATED,
        liquidation_price=None,
        updated_at=_AT,
    )


class _Account:
    """An account that answers what a test sets and counts the requests made of it."""

    def __init__(self, *held: LivePosition) -> None:
        self.held = held
        self.requests = 0
        self.failing = False

    def open_positions(
        self, priority: RequestPriority = RequestPriority.ROUTINE
    ) -> tuple[LivePosition, ...]:
        self.requests += 1
        if self.failing:
            raise ConnectionError("no answer")
        return self.held


def _reads(account: _Account, clock: FakeMonotonicClock) -> VenuePositionReads:
    return VenuePositionReads(
        account.open_positions, clock, SHARED_READING_MAX_AGE_SECONDS
    )


def test_the_bots_of_one_sweep_make_one_request() -> None:
    account, clock = _Account(_position("BTCUSDT", "1")), FakeMonotonicClock()
    reads = _reads(account, clock)

    answers = [reads.positions() for _ in range(20)]

    assert account.requests == 1
    assert all(answer == account.held for answer in answers)


def test_the_next_beat_reads_again() -> None:
    account, clock = _Account(), FakeMonotonicClock()
    reads = _reads(account, clock)
    reads.positions()

    clock.advance(CHECK_EVERY_SECONDS)
    reads.positions()

    assert account.requests == 2


def test_a_reading_is_never_older_than_half_a_beat() -> None:
    account, clock = _Account(), FakeMonotonicClock()
    reads = _reads(account, clock)
    reads.positions()

    clock.advance(SHARED_READING_MAX_AGE_SECONDS - 0.001)
    reads.positions()
    assert account.requests == 1

    clock.advance(0.001)
    reads.positions()
    assert account.requests == 2


def test_half_a_beat_is_inside_a_beat() -> None:
    """The bound that makes the sharing no staler than today's worst case, one beat."""
    assert 0 < SHARED_READING_MAX_AGE_SECONDS < CHECK_EVERY_SECONDS


def test_invalidating_makes_the_next_ask_read_the_account_again() -> None:
    account, clock = _Account(_position("BTCUSDT", "1")), FakeMonotonicClock()
    reads = _reads(account, clock)
    reads.positions()
    account.held = (_position("BTCUSDT", "2"),)

    reads.invalidate()

    assert reads.positions() == account.held
    assert account.requests == 2


def test_a_failed_read_is_raised_and_not_kept() -> None:
    account, clock = _Account(_position("BTCUSDT", "1")), FakeMonotonicClock()
    reads = _reads(account, clock)
    reads.positions()
    clock.advance(CHECK_EVERY_SECONDS)
    account.failing = True

    with pytest.raises(ConnectionError):
        reads.positions()
    account.failing = False
    answer = reads.positions()

    assert answer == account.held
    assert account.requests == 3


class _SlowAccount(_Account):
    """An account whose read waits to be let finish, so a test can act while it is in flight."""

    def __init__(self, *held: LivePosition) -> None:
        super().__init__(*held)
        self.began = threading.Event()
        self.finish = threading.Event()

    def open_positions(
        self, priority: RequestPriority = RequestPriority.ROUTINE
    ) -> tuple[LivePosition, ...]:
        self.began.set()
        assert self.finish.wait(timeout=10)
        return super().open_positions(priority)


def _ask_in_a_thread(
    reads: VenuePositionReads, answers: list[tuple[LivePosition, ...]]
) -> threading.Thread:
    thread = threading.Thread(target=lambda: answers.append(reads.positions()))
    thread.start()
    return thread


def test_bots_asking_while_a_read_is_in_flight_wait_for_it_and_make_no_second_request() -> (
    None
):
    """The read lock: a second bot that arrives while the first is reading takes its answer."""
    account, clock = _SlowAccount(_position("BTCUSDT", "1")), FakeMonotonicClock()
    reads = _reads(account, clock)
    answers: list[tuple[LivePosition, ...]] = []
    first = _ask_in_a_thread(reads, answers)
    assert account.began.wait(timeout=10)
    second = _ask_in_a_thread(reads, answers)

    second.join(timeout=0.3)
    still_waiting = second.is_alive()
    account.finish.set()
    first.join(timeout=10)
    second.join(timeout=10)

    assert still_waiting, "the second bot read instead of waiting for the first"
    assert account.requests == 1
    assert answers == [account.held, account.held]


def test_invalidating_never_waits_for_a_read_in_flight() -> None:
    """An order is never delayed by another bot's slow `positionRisk`."""
    account, clock = _SlowAccount(_position("BTCUSDT", "1")), FakeMonotonicClock()
    reads = _reads(account, clock)
    reader = _ask_in_a_thread(reads, [])
    assert account.began.wait(timeout=10)
    invalidator = threading.Thread(target=reads.invalidate)

    invalidator.start()
    invalidator.join(timeout=2)
    returned = not invalidator.is_alive()
    account.finish.set()
    reader.join(timeout=10)

    assert returned, "invalidate() waited behind a read in flight"


def test_a_read_in_flight_when_the_reading_is_invalidated_is_not_kept() -> None:
    account, clock = _SlowAccount(_position("BTCUSDT", "1")), FakeMonotonicClock()
    reads = _reads(account, clock)
    answers: list[tuple[LivePosition, ...]] = []
    reader = _ask_in_a_thread(reads, answers)
    assert account.began.wait(timeout=10)

    reads.invalidate()  # an order was sent while the read was on its way
    account.finish.set()
    reader.join(timeout=10)
    account.held = (_position("BTCUSDT", "0.5"),)

    assert answers == [
        (_position("BTCUSDT", "1"),)
    ]  # the asker still gets what it read
    assert reads.positions() == account.held  # but nobody after it is served that
    assert account.requests == 2


def test_each_venue_has_its_own_reading() -> None:
    spot, futures = _Account(), _Account(_position("BTCUSDT", "1"))
    ports = Mock()
    ports.get.side_effect = lambda venue: Mock(
        account_snapshot=futures if venue is TradingVenue.FUTURES_TESTNET else spot
    )
    shared = SharedPositionReads(ports, FakeMonotonicClock())

    assert shared.of(TradingVenue.FUTURES_TESTNET) is shared.of(
        TradingVenue.FUTURES_TESTNET
    )
    assert shared.of(TradingVenue.FUTURES_TESTNET) is not shared.of(
        TradingVenue.SPOT_TESTNET
    )
    assert shared.of(TradingVenue.FUTURES_TESTNET).positions() == futures.held
    assert spot.requests == 0


def _gateway(
    account: _Account, reads: VenuePositionReads | None, submission: FakeOrderSubmission
) -> BotOrderGateway:
    ports = Mock()
    ports.account_snapshot = account
    ports.order_submission = submission
    return BotOrderGateway(
        ports,
        BotIdentity("bot:abc123", "abc123", "BTCUSDT"),
        Mock(),
        BotSharedReads(reads),
    )


def test_a_watch_takes_the_shared_reading_and_a_confirmation_asks_the_account() -> None:
    account, clock = _Account(_position("BTCUSDT", "1")), FakeMonotonicClock()
    gateway = _gateway(account, _reads(account, clock), FakeOrderSubmission())

    watched = [gateway.account_reads.watched_position() for _ in range(3)]
    confirmed = gateway.position()

    assert watched == [Decimal(1)] * 3
    assert confirmed == Decimal(1)
    assert account.requests == 2  # one for the three watches, one for the confirmation


def test_a_watch_reads_for_itself_when_no_reading_is_shared() -> None:
    account = _Account(_position("BTCUSDT", "1"))
    gateway = _gateway(account, None, FakeOrderSubmission())

    gateway.account_reads.watched_position()
    gateway.account_reads.watched_position()

    assert account.requests == 2


def test_a_watch_only_counts_the_bots_own_symbol() -> None:
    account, clock = (
        _Account(_position("BTCUSDT", "1"), _position("ETHUSDT", "-5")),
        FakeMonotonicClock(),
    )
    gateway = _gateway(account, _reads(account, clock), FakeOrderSubmission())

    assert gateway.account_reads.watched_position() == Decimal(1)


def test_an_unread_account_is_no_position_not_a_flat_one() -> None:
    account, clock = _Account(), FakeMonotonicClock()
    account.failing = True
    gateway = _gateway(account, _reads(account, clock), FakeOrderSubmission())

    assert gateway.account_reads.watched_position() is None


def test_an_order_sent_drops_the_shared_reading() -> None:
    """The reading says what the account held before the order; the next watch must not."""
    account, clock = _Account(_position("BTCUSDT", "1")), FakeMonotonicClock()
    submission = FakeOrderSubmission()
    submission.submit_answers(ExecuteOrderResult(None, None, (), None))
    gateway = _gateway(account, _reads(account, clock), submission)
    gateway.account_reads.watched_position()
    account.held = (_position("BTCUSDT", "0.5"),)

    gateway.market_sell(Decimal("0.5"), Decimal(100))

    assert gateway.account_reads.watched_position() == Decimal("0.5")


def test_a_read_that_races_an_order_is_not_kept_after_it() -> None:
    """Another bot's watch reads while the order is in flight: the reading it takes is from before
    the order, and must not be served after it (review of `BOT-184`)."""
    account, clock = _Account(_position("BTCUSDT", "1")), FakeMonotonicClock()
    reads = _reads(account, clock)

    class _ReadsMidSend(FakeOrderSubmission):
        def submit(self, request, live=False):  # type: ignore[no-untyped-def]
            reads.positions()
            account.held = (_position("BTCUSDT", "0.5"),)
            return super().submit(request, live=live)

    submission = _ReadsMidSend()
    submission.submit_answers(ExecuteOrderResult(None, None, (), None))
    gateway = _gateway(account, reads, submission)

    gateway.market_sell(Decimal("0.5"), Decimal(100))

    assert gateway.account_reads.watched_position() == Decimal("0.5")


def test_a_fill_the_bot_hears_drops_the_shared_reading() -> None:
    account, clock = _Account(_position("BTCUSDT", "1")), FakeMonotonicClock()
    gateway = _gateway(account, _reads(account, clock), FakeOrderSubmission())
    gateway.account_reads.watched_position()
    account.held = ()

    gateway.account_reads.account_changed()

    assert gateway.account_reads.watched_position() == Decimal(0)


def test_a_cancel_drops_the_shared_reading() -> None:
    account, clock = _Account(_position("BTCUSDT", "1")), FakeMonotonicClock()
    submission = FakeOrderSubmission()
    submission.cancel_answers(CancelOrderResult(None, None))
    gateway = _gateway(account, _reads(account, clock), submission)
    gateway.account_reads.watched_position()
    account.held = (_position("BTCUSDT", "2"),)

    gateway.cancel("SEW-abc123-0123456789")

    assert gateway.account_reads.watched_position() == Decimal(2)

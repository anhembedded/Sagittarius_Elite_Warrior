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

    def open_positions(self) -> tuple[LivePosition, ...]:
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


def test_bots_asking_together_on_different_threads_make_one_request() -> None:
    account, clock = _Account(_position("BTCUSDT", "1")), FakeMonotonicClock()
    reads = _reads(account, clock)
    start = threading.Barrier(8)
    answers: list[tuple[LivePosition, ...]] = []

    def ask() -> None:
        start.wait()
        answers.append(reads.positions())

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert account.requests == 1
    assert len(answers) == 8


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
        ports, BotIdentity("bot:abc123", "abc123", "BTCUSDT"), Mock(), reads
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


def test_a_cancel_drops_the_shared_reading() -> None:
    account, clock = _Account(_position("BTCUSDT", "1")), FakeMonotonicClock()
    submission = FakeOrderSubmission()
    submission.cancel_answers(CancelOrderResult(None, None))
    gateway = _gateway(account, _reads(account, clock), submission)
    gateway.account_reads.watched_position()
    account.held = (_position("BTCUSDT", "2"),)

    gateway.cancel("SEW-abc123-0123456789")

    assert gateway.account_reads.watched_position() == Decimal(2)

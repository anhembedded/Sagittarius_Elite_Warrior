"""`BOT-221` — the two watches of a bot read its symbol's mark once between them, and never judge
on a mark older than half a beat or older than the last order or fill of the symbol.

`SharedMarkReads` is the reading, found by venue and symbol; `WatchedMarkSource` serves a bot's
exit watch and risk watch from it; `BotOrderGateway` and `account_changed` drop it. A confirmation
never takes it, and a failed read is never kept."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_facts import (
    GridFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_account_reads import (
    BotAccountReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    BotIdentity,
    BotOrderGateway,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_shared_reads import (
    BotSharedReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.bounded_age_reading import (
    BoundedAgeReading,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.shared_mark_reads import (
    SharedMarkReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.shared_position_reads import (
    SHARED_READING_MAX_AGE_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.mark_source_futures import (
    read_mark_price,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.bot_price_watch import (
    CHECK_EVERY_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_mark_source import (
    MarkReadError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_monotonic_clock import (
    FakeMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import MarkPrice
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
    FuturesReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_AT = datetime(2026, 10, 21, tzinfo=UTC)
_VENUE = TradingVenue.FUTURES_TESTNET


class _Terms(FakeOrderEntryTerms):
    """The real fake of the venue's terms, counting the `premiumIndex` reads it is asked for."""

    def __init__(self, mark: str) -> None:
        super().__init__(futures=FuturesReads())
        self.requests = 0
        self.price = Decimal(mark)
        self.failing = False
        self.no_mark = False

    def mark_price_for(self, symbol: str) -> MarkPrice | NotApplicable:
        self.requests += 1
        if self.failing:
            return super().mark_price_for("UNSEEDED")  # raises: no mark seeded
        if self.no_mark:
            return NotApplicable.ON_THIS_VENUE
        return MarkPrice(symbol, self.price, _AT)


def _shared(terms: _Terms, clock: FakeMonotonicClock) -> SharedMarkReads:
    ports = Mock()
    ports.get.return_value.order_entry_terms = terms
    return SharedMarkReads(ports, clock)


def test_the_two_watches_of_a_beat_make_one_request() -> None:
    terms, clock = _Terms("100"), FakeMonotonicClock()
    reading = _shared(terms, clock).of(_VENUE, "BTCUSDT")

    answers = [reading.current(), reading.current()]  # the exit watch, the risk watch

    assert terms.requests == 1
    assert answers == [Decimal(100), Decimal(100)]


def test_the_next_beat_reads_again() -> None:
    terms, clock = _Terms("100"), FakeMonotonicClock()
    reading = _shared(terms, clock).of(_VENUE, "BTCUSDT")
    reading.current()

    clock.advance(CHECK_EVERY_SECONDS)
    terms.price = Decimal(90)

    assert reading.current() == Decimal(90)
    assert terms.requests == 2


def test_a_mark_is_never_served_past_half_a_beat() -> None:
    terms, clock = _Terms("100"), FakeMonotonicClock()
    reading = _shared(terms, clock).of(_VENUE, "BTCUSDT")
    reading.current()

    clock.advance(SHARED_READING_MAX_AGE_SECONDS - 0.001)
    reading.current()
    assert terms.requests == 1

    clock.advance(0.001)
    reading.current()
    assert terms.requests == 2


def test_each_symbol_has_its_own_reading() -> None:
    shared = _shared(_Terms("100"), FakeMonotonicClock())

    assert shared.of(_VENUE, "BTCUSDT") is shared.of(_VENUE, "BTCUSDT")
    assert shared.of(_VENUE, "BTCUSDT") is not shared.of(_VENUE, "ETHUSDT")
    assert shared.of(_VENUE, "BTCUSDT") is not shared.of(
        TradingVenue.SPOT_TESTNET, "BTCUSDT"
    )


def test_a_failed_read_is_not_kept_and_says_it_is_no_price() -> None:
    terms, clock = _Terms("100"), FakeMonotonicClock()
    reading = _shared(terms, clock).of(_VENUE, "BTCUSDT")
    terms.failing = True

    with pytest.raises(MarkReadError):
        reading.current()
    terms.failing = False

    assert reading.current() == Decimal(100)
    assert terms.requests == 2


def test_a_venue_with_no_mark_is_an_unread_mark_not_a_price() -> None:
    terms = _Terms("100")
    terms.no_mark = True

    with pytest.raises(MarkReadError):
        read_mark_price(terms, "BTCUSDT")


def _gateway(
    terms: _Terms, clock: FakeMonotonicClock, submission: FakeOrderSubmission
) -> BotOrderGateway:
    ports = Mock()
    ports.order_submission = submission
    reading = _shared(terms, clock).of(_VENUE, "BTCUSDT")
    return BotOrderGateway(
        ports,
        BotIdentity("bot:abc123", "abc123", "BTCUSDT"),
        Mock(),
        BotSharedReads(mark=reading),
    )


def test_an_order_sent_drops_the_mark() -> None:
    """The reading says where the mark was before the order; the next judgement must not."""
    terms, clock = _Terms("100"), FakeMonotonicClock()
    submission = FakeOrderSubmission()
    submission.submit_answers(ExecuteOrderResult(None, None, (), None))
    gateway = _gateway(terms, clock, submission)
    shared = gateway.account_reads.shared_mark
    assert shared is not None
    shared.current()
    terms.price = Decimal(90)

    gateway.market_sell(Decimal("0.5"), Decimal(100))

    assert shared.current() == Decimal(90)


def test_a_fill_heard_drops_the_mark() -> None:
    terms, clock = _Terms("100"), FakeMonotonicClock()
    gateway = _gateway(terms, clock, FakeOrderSubmission())
    shared = gateway.account_reads.shared_mark
    assert shared is not None
    shared.current()
    terms.price = Decimal(90)

    gateway.account_reads.account_changed()  # what `GridFacts.on_fill` does on the stream

    assert shared.current() == Decimal(90)


def test_a_read_that_races_an_order_is_not_kept_after_it() -> None:
    terms, clock = _Terms("100"), FakeMonotonicClock()
    reading = _shared(terms, clock).of(_VENUE, "BTCUSDT")
    reads = BotAccountReads(
        Mock(),
        BotIdentity("bot:abc123", "abc123", "BTCUSDT"),
        BotSharedReads(mark=reading),
    )
    original = terms.mark_price_for

    def read_then_the_order_lands(symbol: str) -> MarkPrice | NotApplicable:
        answer = original(symbol)
        reads.account_changed()  # the order came back while the read was on its way
        return answer

    terms.mark_price_for = read_then_the_order_lands  # type: ignore[method-assign]
    assert reading.current() == Decimal(100)
    terms.mark_price_for = original  # type: ignore[method-assign]
    terms.price = Decimal(90)

    assert reading.current() == Decimal(90)


def test_a_bot_without_a_shared_mark_reads_for_itself() -> None:
    reads = BotAccountReads(Mock(), BotIdentity("bot:abc123", "abc123", "BTCUSDT"))

    assert reads.shared_mark is None
    reads.account_changed()  # nothing to drop, and nothing raised


def test_a_reading_is_aged_from_when_its_request_was_made() -> None:
    """A slow read must not look younger than it is: begun at 0 and answered at 2 s, it is past
    the half-beat bound 0.6 s later, though only 0.6 s old by the time of its answer."""
    clock = FakeMonotonicClock()
    reads: list[int] = []

    def slow_read() -> int:
        clock.advance(2.0)
        reads.append(1)
        return len(reads)

    reading = BoundedAgeReading(slow_read, clock, SHARED_READING_MAX_AGE_SECONDS)
    reading.current()
    clock.advance(SHARED_READING_MAX_AGE_SECONDS - 2.0 + 0.1)

    reading.current()

    assert len(reads) == 2


def test_a_fill_heard_by_the_stream_drops_the_mark_before_any_order_follows() -> None:
    """`GridFacts.on_fill` drops the symbol's reading on the stream's thread, on its own: the
    order the grid places after a fill would drop it too, so this is the case with none."""
    terms, clock = _Terms("100"), FakeMonotonicClock()
    gateway = _gateway(terms, clock, FakeOrderSubmission())
    shared = gateway.account_reads.shared_mark
    assert shared is not None
    shared.current()
    terms.price = Decimal(90)
    context = Mock(spec=GridRunContext)
    context.gateway = gateway
    facts = GridFacts(context, Mock(), lambda _what, _apply: None, lambda: None)

    facts.on_fill(Mock(client_order_id="bot:abc123-1"))

    assert shared.current() == Decimal(90)

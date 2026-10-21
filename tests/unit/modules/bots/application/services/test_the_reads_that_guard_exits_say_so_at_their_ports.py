"""`BOT-226` — a bot's position, mark price and open protective stops are read as exit guards.

@details Classed at the ports (`IAccountSnapshot.open_positions`, `IOrderEntryTerms.mark_price_for`,
`IAccountActivity.open_orders`), by what the fact is for: the three the exits are judged on name
`EXIT_GUARD`, every ladder read stays `ROUTINE` and waits at the 70 % line. The fakes record the
priority each read named, so a read that stops naming it fails here, whichever call site makes it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_account_reads import (
    BotAccountReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_identity import (
    BotIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.shared_mark_reads import (
    SharedMarkReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.shared_position_reads import (
    SharedPositionReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.mark_source_futures import (
    read_mark_price,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_monotonic_clock import (
    FakeMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import (
    MarkPrice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
    FuturesReads,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_IDENTITY = BotIdentity("bot.abc123", "abc123", "BTCUSDT")
_VENUE = TradingVenue.FUTURES_TESTNET
_GUARD = RequestPriority.EXIT_GUARD


def _mark() -> MarkPrice:
    return MarkPrice(symbol="BTCUSDT", mark_price=Decimal(100), as_of=datetime.now(UTC))


class _World:
    def __init__(self) -> None:
        self.snapshot = FakeAccountSnapshot()
        self.activity = FakeAccountActivity()
        self.terms = FakeOrderEntryTerms(
            futures=FuturesReads(marks={"BTCUSDT": _mark()})
        )
        self.ports = SimpleNamespace(
            account_snapshot=self.snapshot,
            account_activity=self.activity,
            order_entry_terms=self.terms,
        )
        self.reads = BotAccountReads(self.ports, _IDENTITY)  # type: ignore[arg-type]


def test_the_bots_position_is_read_as_an_exit_guard() -> None:
    world = _World()

    world.reads.position()

    assert world.snapshot.position_priorities == [_GUARD]


def test_the_bots_open_stops_are_read_as_an_exit_guard() -> None:
    world = _World()

    world.reads.protective_orders()

    assert world.activity.open_order_priorities == [_GUARD]


def test_every_ladder_read_stays_routine_and_waits_at_the_70_percent_line() -> None:
    world = _World()

    world.reads.ladder_orders()

    assert world.activity.open_order_priorities == [RequestPriority.ROUTINE]


def test_the_mark_the_exits_are_judged_on_is_read_as_an_exit_guard() -> None:
    world = _World()

    assert read_mark_price(world.terms, "BTCUSDT") == Decimal(100)

    assert world.terms.mark_priorities == [_GUARD]


def test_the_venues_shared_reading_of_positions_is_an_exit_guard() -> None:
    world = _World()
    shared = SharedPositionReads(
        Mock(get=Mock(return_value=world.ports)),
        FakeMonotonicClock(),  # type: ignore[arg-type]
    )

    shared.of(_VENUE).positions()

    assert world.snapshot.position_priorities == [_GUARD]


def test_the_shared_mark_reading_is_an_exit_guard() -> None:
    world = _World()
    shared = SharedMarkReads(
        Mock(get=Mock(return_value=world.ports)), FakeMonotonicClock()
    )  # type: ignore[arg-type]

    shared.of(_VENUE, "BTCUSDT").current()

    assert world.terms.mark_priorities == [_GUARD]

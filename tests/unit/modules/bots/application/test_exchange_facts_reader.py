"""`BOT-174` — the exchange snapshot of one bot, read over the venue's ports.

@details The reader never raises and never turns a failed read into an empty
account: a read that did not answer is `ExchangeUnavailable` with the reason in
words. Every collaborator is its verified fake.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exchange_facts_reader import (
    ExchangeFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeLoaded,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import (
    OrderType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_account_snapshot import (
    a_funded_status,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    readiness_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    SYMBOL,
)

VENUE = TradingVenue.SPOT_TESTNET
OTHER_BOT = "zzz999"


def _holding(asset: str, free: str, locked: str = "0") -> SpotHolding:
    return SpotHolding(asset, Decimal(free), Decimal(locked), Decimal("0.00000001"))


def _order(
    tag: str | None,
    side: OrderSide,
    quantity: str,
    price: str = "100",
    symbol: str = SYMBOL,
) -> Order:
    prefix = f"SEW-{tag}-" if tag else "SEW-"
    return Order(
        client_order_id=ClientOrderId(f"{prefix}{'a' * (10 if tag else 12)}"),
        symbol=symbol,
        side=side,
        order_type=OrderType.LIMIT,
        quantity=Decimal(quantity),
        price=Decimal(price),
    )


class _Fakes:
    """The venue the reader asks, and the bot it asks about."""

    def __init__(self, world: ReadinessWorld) -> None:
        self.account = FakeAccountSnapshot(a_funded_status(VENUE))
        self.activity = FakeAccountActivity()
        self.session = FakeTradingSession()
        self.ports = FakeVenueTradingPorts(
            fake_venue_ports(
                VENUE,
                account_snapshot=self.account,
                account_activity=self.activity,
                trading_session=self.session,
            )
        )
        self.reader = ExchangeFactsReader(self.ports, world.clock)
        self.bot: Bot = world.store.load(BotId(BOT)).bot

    def hold(self, *holdings: SpotHolding, available: str = "5000") -> None:
        status = replace(
            a_funded_status(VENUE, Decimal(available)), holdings=tuple(holdings)
        )
        self.account.answer_with(status)


@pytest.fixture
def fakes() -> _Fakes:
    return _Fakes(readiness_world())


def _facts(fakes: _Fakes):
    snapshot = fakes.reader.read(fakes.bot)
    assert isinstance(snapshot, ExchangeLoaded), snapshot
    return snapshot.facts


def test_the_free_and_locked_base_and_quote_are_read_apart(fakes: _Fakes) -> None:
    fakes.hold(
        _holding("BTC", "0.4", "0.1"), _holding("USDT", "5000", "250"), available="5000"
    )

    facts = _facts(fakes)

    assert (facts.base_asset, facts.quote_asset) == ("BTC", "USDT")
    assert (facts.base_free, facts.base_locked) == (Decimal("0.4"), Decimal("0.1"))
    assert (facts.quote_free, facts.quote_locked) == (Decimal(5000), Decimal(250))
    assert facts.venue_title == "Spot Testnet"
    assert facts.can_trade is True


def test_a_base_the_account_does_not_hold_is_zero_free_and_zero_locked(
    fakes: _Fakes,
) -> None:
    fakes.hold(_holding("USDT", "5000"))

    facts = _facts(fakes)

    assert (facts.base_free, facts.base_locked) == (Decimal(0), Decimal(0))


def test_the_bots_own_orders_are_told_from_everyone_elses_on_the_symbol(
    fakes: _Fakes,
) -> None:
    fakes.hold(_holding("BTC", "0.1", "0.5"), _holding("USDT", "100", "900"))
    fakes.activity.holding_open_orders(
        [
            _order(BOT, OrderSide.SELL, "0.2"),
            _order(BOT, OrderSide.SELL, "0.1"),
            _order(BOT, OrderSide.BUY, "2", "200"),
            _order(OTHER_BOT, OrderSide.SELL, "0.2"),
            _order(None, OrderSide.BUY, "1"),
            _order(BOT, OrderSide.SELL, "9", symbol="ETHUSDT"),
        ]
    )

    facts = _facts(fakes)

    assert facts.own_open_orders == 3
    assert facts.foreign_open_orders == 2
    assert facts.own_sell_base == Decimal("0.3")
    assert facts.own_buy_quote == Decimal(400)


def test_the_bots_reserve_never_exceeds_what_the_exchange_says_is_locked(
    fakes: _Fakes,
) -> None:
    """A part-filled SELL locks less than it was placed for."""
    fakes.hold(_holding("BTC", "0", "0.15"), _holding("USDT", "0", "50"))
    fakes.activity.holding_open_orders(
        [_order(BOT, OrderSide.SELL, "0.2"), _order(BOT, OrderSide.BUY, "2", "100")]
    )

    facts = _facts(fakes)

    assert facts.own_sell_base == Decimal("0.15")
    assert facts.own_buy_quote == Decimal(50)


def test_what_earlier_runs_left_is_asked_of_the_session_for_this_bot(
    fakes: _Fakes,
) -> None:
    fakes.session.earlier_runs_answers(
        EarlierRunsInventory(Decimal("0.02"), Decimal(2000))
    )

    facts = _facts(fakes)

    assert facts.earlier_runs.quantity == Decimal("0.02")
    (request,) = fakes.session.earlier_runs_requests
    assert (request.tag, request.symbol, request.base_asset) == (BOT, SYMBOL, "BTC")
    assert request.since == fakes.bot.created_at


def test_what_earlier_runs_left_not_being_known_stays_unknown(fakes: _Fakes) -> None:
    fakes.session.earlier_runs_answers(EarlierRunsInventory(unavailable="no history"))

    facts = _facts(fakes)

    assert not facts.earlier_runs.is_known
    assert facts.earlier_runs.unavailable == "no history"


def test_an_account_that_could_not_be_read_is_unavailable_with_the_reason(
    fakes: _Fakes,
) -> None:
    fakes.account.answer_with(
        replace(
            a_funded_status(VENUE),
            reachable=False,
            failure=ConnectionFailureKind.NETWORK,
        )
    )

    snapshot = fakes.reader.read(fakes.bot)

    assert isinstance(snapshot, ExchangeUnavailable)
    assert snapshot.reason == "Not connected: exchange unreachable"
    assert fakes.session.earlier_runs_requests == []


def test_balances_that_were_not_read_are_unavailable_never_an_empty_account(
    fakes: _Fakes,
) -> None:
    fakes.account.answer_with(replace(a_funded_status(VENUE), holdings=None))

    snapshot = fakes.reader.read(fakes.bot)

    assert isinstance(snapshot, ExchangeUnavailable)
    assert "balances were not read" in snapshot.reason


def test_open_orders_that_could_not_be_read_are_unavailable_never_an_empty_list(
    fakes: _Fakes,
) -> None:
    fakes.activity.open_orders_raise(ConnectionError("rate limited"))

    snapshot = fakes.reader.read(fakes.bot)

    assert isinstance(snapshot, ExchangeUnavailable)
    assert "open orders were not read" in snapshot.reason
    assert "rate limited" in snapshot.reason


def test_a_venue_that_is_not_enabled_is_unavailable_and_says_so(
    fakes: _Fakes,
) -> None:
    mainnet_bot = replace(
        fakes.bot,
        definition=replace(fakes.bot.definition, venue=TradingVenue.SPOT_MAINNET),
    )

    snapshot = fakes.reader.read(mainnet_bot)

    assert isinstance(snapshot, ExchangeUnavailable)
    assert "not enabled" in snapshot.reason


def test_what_was_read_is_logged_under_its_tag_at_debug(
    fakes: _Fakes, caplog: pytest.LogCaptureFixture
) -> None:
    fakes.hold(_holding("BTC", "0.4", "0.1"), _holding("USDT", "5000"))

    with caplog.at_level(logging.DEBUG, logger="App.Bots.Readiness"):
        _facts(fakes)

    assert "BTC free 0.4 locked 0.1" in caplog.text
    assert "[exchange-facts]" in caplog.text


def test_a_snapshot_that_is_unavailable_is_logged_at_info_with_its_reason(
    fakes: _Fakes, caplog: pytest.LogCaptureFixture
) -> None:
    fakes.activity.open_orders_raise(ConnectionError("rate limited"))

    with caplog.at_level(logging.INFO, logger="App.Bots.Readiness"):
        fakes.reader.read(fakes.bot)

    (record,) = [r for r in caplog.records if "[exchange-facts]" in r.getMessage()]
    assert record.levelno == logging.INFO
    assert "rate limited" in record.getMessage()

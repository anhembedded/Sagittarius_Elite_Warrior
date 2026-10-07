"""`EPIC-028O` — a Futures market fill, end to end through the real adapters
and `python-binance` over HTTP: the order reads back `FILLED` at the book,
its trade carries the fee and the realized PnL, the position's entry price
is the volume-weighted average of its fills, the account summary moves by
the fees and PnL, and a Multi-Assets account is read from its account-wide
figures.

@details The fake fills a buy at the ask (64 000.1) and a sell at the bid
(63 999.9), charges 0.05 % taker, and marks BTCUSDT at 64 000.0
(`tests/sanity/fake_exchange/futures_account_state.py`). Expected figures
are worked out from those rules below each test, not read back from the
code under test.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_reader import (
    FuturesHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AssetMode,
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server

_ASK = Decimal("64000.1")
_BID = Decimal("63999.9")
_FEE = Decimal("0.0005")


class _Credentials(IExchangeCredentialsProvider):
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used by this test")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


@contextmanager
def _fake_exchange() -> Iterator[FakeServerUrls]:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        yield urls


def _trading() -> FuturesTradingClient:
    sessions = FuturesSessionFactory()
    return FuturesTradingClient(
        sessions,
        _Credentials(),
        FuturesMetadataProvider(sessions, InMemorySymbolOrderMetadataCache()),
        OrderSubmissionMode.LIVE,
    )


def _market(cid: str, side: OrderSide, quantity: str, *, reduce: bool = False) -> Order:
    return Order(
        client_order_id=ClientOrderId(cid),
        symbol="BTCUSDT",
        side=side,
        order_type=OrderType.MARKET,
        quantity=Decimal(quantity),
        reduce_only=reduce,
    )


def _summary() -> FuturesAccountSummary:
    summary = (
        FuturesAccountReader(FuturesSessionFactory(), _Credentials())
        .check_connection()
        .summary
    )
    assert isinstance(summary, FuturesAccountSummary)
    return summary


def _week_ago() -> datetime:
    return datetime.now(UTC) - timedelta(days=7)


def test_a_market_fill_reads_back_filled_with_its_trade_and_fee() -> None:
    with _fake_exchange():
        _trading().place_order(_market("SEW-ff-buy-000001", OrderSide.BUY, "0.010"))
        history = FuturesHistoryReader(FuturesSessionFactory(), _Credentials())
        (record,) = history.order_history("BTCUSDT", _week_ago())
        (trade,) = history.trade_history("BTCUSDT", _week_ago())

    assert record.order.status is OrderStatus.FILLED
    assert (record.executed_quantity, record.average_price) == (Decimal("0.010"), _ASK)
    assert (trade.side, trade.price, trade.quantity) == (
        OrderSide.BUY,
        _ASK,
        Decimal("0.010"),
    )
    # 0.010 × 64 000.1 × 0.05 % = 0.3200005
    assert trade.fee == Decimal("0.32000050")
    assert trade.fee_asset == "USDT"
    assert trade.realized_pnl == 0


def test_two_buys_average_their_entry_and_a_close_realizes_the_difference() -> None:
    """Entry is volume-weighted across both buys; the reduce-only sell closes
    all of it at the bid and books `(bid − entry) × quantity`."""
    with _fake_exchange():
        trading = _trading()
        trading.place_order(_market("SEW-ff-buy-000002", OrderSide.BUY, "0.010"))
        trading.place_order(_market("SEW-ff-buy-000003", OrderSide.BUY, "0.030"))
        (position,) = trading.get_positions("BTCUSDT")
        trading.place_order(
            _market("SEW-ff-sell-00004", OrderSide.SELL, "0.100", reduce=True)
        )
        flat = trading.get_positions("BTCUSDT")
        history = FuturesHistoryReader(FuturesSessionFactory(), _Credentials())
        trades = history.trade_history("BTCUSDT", _week_ago())
        orders = history.order_history("BTCUSDT", _week_ago())
        summary = _summary()

    # Both buys fill at the ask, so the weighted entry is the ask.
    assert position.position_amt == Decimal("0.040")
    assert position.entry_price == _ASK
    assert flat == []
    closing = trades[-1]
    # Reduce-only caps the sell at the 0.040 held; the order still shows the
    # 0.100 sent.
    assert (closing.side, closing.quantity) == (OrderSide.SELL, Decimal("0.040"))
    closing_order = orders[-1]
    assert closing_order.order.quantity == Decimal("0.100")
    assert closing_order.executed_quantity == Decimal("0.040")
    # (63 999.9 − 64 000.1) × 0.040 = −0.008
    assert closing.realized_pnl == Decimal("-0.00800000")
    fees = sum((trade.fee for trade in trades), Decimal(0))
    assert summary.wallet_balance == Decimal(15000) - fees + closing.realized_pnl
    assert summary.unrealized_pnl == 0
    assert summary.asset_mode is AssetMode.SINGLE_ASSET


def test_an_open_long_shows_in_the_summary_at_the_mark() -> None:
    with _fake_exchange():
        _trading().place_order(_market("SEW-ff-buy-000005", OrderSide.BUY, "0.100"))
        summary = _summary()

    # (64 000.0 − 64 000.1) × 0.100 = −0.01 unrealized at the mark.
    assert summary.unrealized_pnl == Decimal("-0.01000000")
    assert summary.margin_balance == summary.wallet_balance + summary.unrealized_pnl
    # 20x by default: 0.100 × 64 000.0 ÷ 20 = 320 of initial margin.
    assert summary.available_balance == summary.margin_balance - Decimal(320)


def test_a_reduce_only_order_with_nothing_to_reduce_is_refused() -> None:
    with _fake_exchange() as urls:
        status, body = urls.futures_book.place(
            {
                "symbol": "BTCUSDT",
                "side": "SELL",
                "type": "MARKET",
                "quantity": "0.010",
                "reduceOnly": "true",
                "newClientOrderId": "SEW-ff-reduce-0006",
            }
        )

    assert (status, body["code"]) == (400, -2022)


def test_a_multi_assets_account_is_read_from_its_account_wide_figures() -> None:
    with _fake_exchange() as urls:
        urls.futures_book.account.multi_assets = True
        summary = _summary()

    # 15 000 USDT plus the fake's 600 USD of BNB margin; the USDT row alone
    # would read 15 000.
    assert summary.asset_mode is AssetMode.MULTI_ASSETS
    assert summary.wallet_balance == Decimal(15600)
    assert summary.available_balance == Decimal(15600)

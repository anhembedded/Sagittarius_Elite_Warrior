"""`EPIC-028H` — the Spot `BTCUSDT` terms and account the order-panel tests
share, so each test states only what it changes."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    SpotAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    OrderEntryContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

SYMBOL = "BTCUSDT"
STEP = Decimal("0.001")
MARKET_STEP = Decimal("0.01")
TAKER = Decimal("0.001")

TERMS = OrderEntryTerms(
    rules=SymbolOrderMetadata(
        symbol=SYMBOL,
        status="TRADING",
        step_size=STEP,
        tick_size=Decimal("0.01"),
        min_notional=Decimal(10),
        quantity_precision=None,
        price_precision=None,
        fetched_at=datetime(2026, 9, 30, tzinfo=UTC),
        market_step_size=MARKET_STEP,
    ),
    commission=CommissionRate(SYMBOL, maker=Decimal("0.0008"), taker=TAKER),
)


def spot_context(
    available_quote: Decimal | None = Decimal(1000),
    free_base: Decimal | None = Decimal("0.5"),
    notional_limit: Decimal | None = None,
) -> OrderEntryContext:
    return OrderEntryContext(
        symbol=SYMBOL,
        base_asset="BTC",
        quote_asset="USDT",
        terms=TERMS,
        available_quote=available_quote,
        free_base=free_base,
        notional_limit=notional_limit,
    )


def spot_status(
    quote_free: Decimal = Decimal(1000), btc_free: Decimal | None = Decimal("0.5")
) -> ExchangeConnectionStatus:
    """A reachable Spot account holding `quote_free` USDT and, unless
    `btc_free` is `None`, that much BTC."""
    holdings = [
        SpotHolding("USDT", quote_free, Decimal(0), dust_threshold=Decimal("0.01"))
    ]
    if btc_free is not None:
        holdings.append(
            SpotHolding("BTC", btc_free, Decimal(0), dust_threshold=Decimal("0.00001"))
        )
    return ExchangeConnectionStatus(
        venue=TradingVenue.SPOT_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=0,
        usdt_balance=quote_free,
        position_mode=None,
        margin_type=None,
        open_position_count=0,
        holdings=tuple(holdings),
        summary=SpotAccountSummary(
            venue=TradingVenue.SPOT_TESTNET,
            available_balance=quote_free,
            equity=None,
            quote_asset="USDT",
            quote_free=quote_free,
            quote_locked=Decimal(0),
        ),
    )


class InlineThreadManager(IThreadManager):
    """Runs each task at once on the caller's thread."""

    def __init__(self) -> None:
        self.submitted: list[Callable[..., Any]] = []

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        self.submitted.append(task)
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None


class HeldThreadManager(IThreadManager):
    """Keeps each task until the test runs it, so a test can supersede an
    action while its answer is still out."""

    def __init__(self) -> None:
        self.pending: list[tuple[Callable[..., Any], tuple[Any, ...]]] = []

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        self.pending.append((task, args))
        return concurrent.futures.Future()

    def run(self, index: int) -> None:
        task, args = self.pending[index]
        task(*args)

    def shutdown(self, wait: bool = True) -> None:
        return None

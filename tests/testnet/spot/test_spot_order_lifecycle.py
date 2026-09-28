"""`EPIC-027P` — the one Spot Testnet round trip this tier proves: a small
MARKET BUY makes the target asset's holding appear (read the way
`HoldingsRefreshService`/the Holdings table do, through
`ITradingAccountReader.check_connection()`), then a MARKET SELL of exactly
what was received returns the holding to its pre-trade baseline. Opt-in
only — see `conftest.py` for the two gates.

@details Waits on a *named condition* (the reported holding, polled on a
bounded loop) — never a blind `sleep` (`testing-rule.md` §2), mirroring
`tests/testnet/test_order_lifecycle.py`'s own `_wait_until_position`. Spot
has no position to poll (`SpotTradingClient.get_positions()` always
answers `[]` — a Spot account's shape is a balance, not a position,
`EPIC-027K`); the authoritative fact this tier waits on is the same
`SpotAccountReader.check_connection().holdings` read the live Holdings
table itself is driven by, so a green run here is real evidence the same
mechanism the UI depends on moves for real money's worth on Spot Testnet
credentials.

Asserts invariants (the order left no open remainder — the real MARKET-
fills-immediately-on-Spot fact `test_fake_exchange_spot_routes.py`'s
fixture already encodes — and the holding returns to baseline within a fee
tolerance), never prices. Cleans up in `finally`: a run that leaves a
surplus holding corrupts the baseline the next run reads.

`_QUANTITY` is deliberately small: `0.0002` BTC clears Binance Spot's
documented `NOTIONAL` minimum (5 USDT) at any realistic BTCUSDT price by a
wide margin, and is well above its `LOT_SIZE` step (`0.00001`, per
`test_fake_exchange_spot_routes.py`'s own fixture, itself read from
Binance's public filter documentation) — verification note: not
re-confirmed against a live call (egress to `*.binance.*` is policy-blocked
in this sandbox, same disclosure `SpotAccountReader`'s own module docstring
already makes); the user's own run of this tier is what confirms it against
the real, current Testnet filters.
"""

from __future__ import annotations

import time
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)

_SYMBOL = "BTCUSDT"
_ASSET = "BTC"
_QUANTITY = Decimal("0.0002")
_POLL_INTERVAL_S = 1.0
_TIMEOUT_S = 30.0

#: Real Spot fee (0.1 % base rate, `spot_account_state.py`'s own fixture
#: reasoning) is charged in the asset received on each leg — the BUY's fee
#: shrinks what actually lands, the SELL's fee shrinks the quote proceeds,
#: neither of which is `_QUANTITY` itself. A "back to baseline" holding
#: comparison therefore needs slack wider than the fill amount's own fee,
#: not an exact-zero check — one full fee's worth of `_QUANTITY` is a
#: generous, still-tight bound.
_BASELINE_TOLERANCE = _QUANTITY * Decimal("0.01")

_ROUNDING = OrderQuantityRoundingPolicy()


class _StaticCredentialsProvider:
    def __init__(self, credentials: ExchangeCredentials) -> None:
        self._credentials = credentials

    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(self._credentials, CredentialsSource.ENV)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise NotImplementedError("not used by this tier")


def _holding_free(status: ExchangeConnectionStatus, asset: str) -> Decimal:
    holding = next((h for h in status.holdings or () if h.asset == asset), None)
    return holding.free if holding is not None else Decimal(0)


def _wait_until_holding_free(
    account_reader: SpotAccountReader, asset: str, predicate
) -> Decimal:
    """@brief Polls `check_connection()` until `predicate(free)` accepts
    the result, or raises `TimeoutError` — the named condition this file's
    own docstring describes, not a blind sleep."""
    deadline = time.monotonic() + _TIMEOUT_S
    while time.monotonic() < deadline:
        status = account_reader.check_connection()
        assert status.reachable, status.failure
        free = _holding_free(status, asset)
        if predicate(free):
            return free
        time.sleep(_POLL_INTERVAL_S)
    raise TimeoutError(
        f"{asset} holding did not reach the expected state within {_TIMEOUT_S}s"
    )


def _build_collaborators(
    spot_testnet_credentials: ExchangeCredentials,
) -> tuple[SpotTradingClient, SpotAccountReader, SpotMetadataProvider]:
    session_factory = SpotSessionFactory()
    metadata_provider = SpotMetadataProvider(
        session_factory, InMemorySymbolOrderMetadataCache()
    )
    credentials_provider = _StaticCredentialsProvider(spot_testnet_credentials)
    client = SpotTradingClient(
        session_factory,
        credentials_provider,
        metadata_provider,
        OrderSubmissionMode.LIVE,
    )
    account_reader = SpotAccountReader(session_factory, credentials_provider)
    return client, account_reader, metadata_provider


def test_market_buy_then_sell_returns_the_holding_to_baseline(
    spot_testnet_credentials: ExchangeCredentials,
) -> None:
    client, account_reader, metadata_provider = _build_collaborators(
        spot_testnet_credentials
    )
    metadata = metadata_provider.get_or_fetch(_SYMBOL)
    assert metadata is not None
    step = metadata.step_size_for(OrderType.MARKET)

    baseline_status = account_reader.check_connection()
    assert baseline_status.reachable, baseline_status.failure
    baseline = _holding_free(baseline_status, _ASSET)

    buy = Order(
        client_order_id=generate_client_order_id(),
        symbol=_SYMBOL,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=_QUANTITY,
    )
    try:
        client.place_order(buy)
        # A filled MARKET order leaves no open remainder — the real,
        # fills-immediately-on-Spot fact this tier's own module docstring
        # names — so its absence here is the FILLED proof, not a status
        # field on `place_order()`'s own return (its contract says the
        # returned `Order` is unchanged; the authoritative lifecycle is
        # what this account read, and the Spot User Data Stream in the
        # live app, report — `EPIC-027L`).
        assert buy.client_order_id not in {
            o.client_order_id for o in client.get_open_orders(_SYMBOL)
        }
        after_buy = _wait_until_holding_free(
            account_reader, _ASSET, lambda f: f > baseline
        )

        received = _ROUNDING.round_quantity_down(after_buy - baseline, step)
        assert received > 0, (
            "the BUY fill was too small to round to a sellable quantity"
        )

        sell = Order(
            client_order_id=generate_client_order_id(),
            symbol=_SYMBOL,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=received,
        )
        client.place_order(sell)
        assert sell.client_order_id not in {
            o.client_order_id for o in client.get_open_orders(_SYMBOL)
        }
        final = _wait_until_holding_free(
            account_reader, _ASSET, lambda f: abs(f - baseline) <= _BASELINE_TOLERANCE
        )
        assert abs(final - baseline) <= _BASELINE_TOLERANCE
    finally:
        # Safety net: never leave a real surplus holding for the next run,
        # regardless of which assertion above failed.
        surplus_status = account_reader.check_connection()
        surplus = _holding_free(surplus_status, _ASSET) - baseline
        rounded_surplus = _ROUNDING.round_quantity_down(surplus, step)
        if rounded_surplus > 0:
            client.place_order(
                Order(
                    client_order_id=generate_client_order_id(),
                    symbol=_SYMBOL,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=rounded_surplus,
                )
            )

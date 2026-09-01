"""EPIC-021C runnable milestone — see task §5.

Pulls real Futures Testnet symbol metadata (step size, tick size, min
notional) and shows what `OrderQuantityRoundingPolicy` actually decides for
one or more candidate order quantities — the decision that matters, not the
raw filter table (that's on Binance's own site already).

Run from the superproject root with the venv Python:
    PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
        Sagittarius_Elite_Warrior/scripts/epic021c_metadata_probe.py \
        --symbol BTCUSDT --price 64000 --qty 0.0137 --qty 0.0011

Pass --offline to serve the request from a local fake server
(`tests/sanity/binance_fake_server.py`) instead of the real network — this
sandbox's egress to every `*.binance.*` domain is policy-blocked, so
--offline is how this milestone runs here. On a machine with real network
access, omit it to pull the actual Futures Testnet catalog.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance.client import Client

from Sagittarius_Elite_Warrior.src.domain.policies.order_quantity_rounding_policy import (
    NotionalCheck,
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.futures_symbol_metadata_cache import (
    InMemoryFuturesSymbolMetadataCache,
)

_policy = OrderQuantityRoundingPolicy()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--price", required=True, type=Decimal)
    parser.add_argument(
        "--qty", required=True, type=Decimal, action="append", dest="quantities"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Serve the request from a local fake server instead of the real network.",
    )
    return parser.parse_args()


def _run(symbol: str, price: Decimal, quantities: list[Decimal]) -> None:
    session_factory = ExchangeSessionFactory(MarketDataVenue.MAINNET_PUBLIC)
    provider = FuturesMetadataProvider(
        session_factory, InMemoryFuturesSymbolMetadataCache()
    )
    metadata = provider.get_or_fetch(symbol)
    if metadata is None:
        print(f"{symbol}: không tìm thấy trong catalog futures testnet.")
        return

    print(
        f"{symbol}  stepSize={metadata.step_size}  tickSize={metadata.tick_size}  "
        f"minNotional={metadata.min_notional}  qtyPrec={metadata.quantity_precision}"
    )
    rounded_price = _policy.round_price_to_tick(
        price, metadata.tick_size, OrderSide.BUY
    )
    for raw_qty in quantities:
        accepted_qty = _policy.round_quantity_down(raw_qty, metadata.step_size)
        notional = accepted_qty * rounded_price
        check = _policy.is_notional_sufficient(
            accepted_qty, rounded_price, metadata.min_notional
        )
        verdict = (
            "HỢP LỆ" if check is NotionalCheck.SUFFICIENT else "TỪ CHỐI (MIN_NOTIONAL)"
        )
        comparator = "≥" if check is NotionalCheck.SUFFICIENT else "<"
        print(
            f"  qty {raw_qty} → {accepted_qty}   notional {notional:.2f} USDT"
            f"  {comparator}  {metadata.min_notional} → {verdict}"
        )


def main() -> None:
    args = _parse_args()
    if args.offline:
        sys.path.insert(
            0, str(Path(__file__).resolve().parents[1] / "tests" / "sanity")
        )
        # Not a package import — reachable only via the sys.path.insert
        # above, same as EPIC-021A's fake-server-backed integration test.
        from binance_fake_server import (  # type: ignore[import-not-found]
            run_binance_fake_server,
        )

        with (
            run_binance_fake_server() as urls,
            patch.object(Client, "API_TESTNET_URL", urls.spot),
            patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
        ):
            _run(args.symbol, args.price, args.quantities)
    else:
        _run(args.symbol, args.price, args.quantities)


if __name__ == "__main__":
    main()

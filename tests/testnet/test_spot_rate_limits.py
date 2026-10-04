"""`EPIC-029H` — how many owner budgets one Spot Testnet account holds.

`EPIC-029A` handed this over: the build container cannot reach Binance. The
O1 caps (`OwnerBudgetCaps`) bound each bot's budget, while the venue's
`ORDERS` rate limits and the symbol's `MAX_NUM_ORDERS` bound the whole
account. So the number that matters is how many owners at the caps fit,
counting a burst within each `ORDERS` window (the spacing bounds it) and the
open orders. It goes to `logs/testnet/spot_rate_limits.json`, which answers
whether several bots need an account-wide cap.

The caps are read from an unbooted app built from the shipped config; no
trading is turned on. Opt-in only, behind this tree's two gates
(`conftest.py`).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.tests.testnet.grid_testnet_app import (
    SPOT,
    SYMBOL,
    spot_testnet_config,
    write_report,
)

_WINDOW_S = {"SECOND": 1, "MINUTE": 60, "HOUR": 3600, "DAY": 86400}


def _owner_orders_in(window_s: int, caps: OwnerBudgetCaps) -> int:
    """The most orders one owner at the caps can send in `window_s`: its
    spacing bounds a burst, its per-minute rate bounds anything longer."""
    spacing_s = caps.min_order_spacing.total_seconds()
    by_spacing = math.floor(window_s / spacing_s) + 1 if spacing_s > 0 else math.inf
    by_rate = (
        math.ceil(caps.max_orders_per_minute * window_s / 60)
        if window_s >= 60
        else caps.max_orders_per_minute
    )
    return int(min(by_spacing, by_rate))


def _max_num_orders(info: dict[str, Any]) -> int:
    symbol = next(row for row in info["symbols"] if row["symbol"] == SYMBOL)
    found = next(
        row for row in symbol["filters"] if row["filterType"] == "MAX_NUM_ORDERS"
    )
    return int(found.get("maxNumOrders", found.get("limit")))


def test_how_many_owner_budgets_one_account_holds(
    spot_testnet_credentials: ExchangeCredentials, tmp_path: Path
) -> None:
    engine = create_app(spot_testnet_config(tmp_path))
    try:
        caps = engine.context.container.resolve(OwnerBudgetCaps)
    finally:
        engine.stop()
    info = SpotSessionFactory().create_metadata_client().get_exchange_info()
    orders = [row for row in info["rateLimits"] if row["rateLimitType"] == "ORDERS"]
    max_num_orders = _max_num_orders(info)
    windows = []
    for limit in orders:
        window_s = _WINDOW_S[limit["interval"]] * int(limit["intervalNum"])
        per_owner = _owner_orders_in(window_s, caps)
        windows.append(
            {
                **limit,
                "window_s": window_s,
                "one_owner_at_the_caps": per_owner,
                "owners_that_fit": int(limit["limit"]) // per_owner,
            }
        )
    owners_by_open_orders = max_num_orders // caps.max_open_orders
    owners_that_fit = min(
        [owners_by_open_orders, *(window["owners_that_fit"] for window in windows)]
    )
    write_report(
        "spot_rate_limits.json",
        {
            "venue": SPOT.value,
            "symbol": SYMBOL,
            "orders_rate_limits": windows,
            "max_num_orders": max_num_orders,
            "owners_by_open_orders": owners_by_open_orders,
            "owners_that_fit": owners_that_fit,
            "caps": {
                "max_open_orders": caps.max_open_orders,
                "max_orders_per_minute": caps.max_orders_per_minute,
                "min_order_spacing_ms": caps.min_order_spacing.total_seconds() * 1000,
            },
        },
    )

    assert orders, "the venue publishes no ORDERS rate limit"
    assert owners_that_fit >= 1, "one owner at the caps does not fit the account"

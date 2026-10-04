"""`EPIC-029A` (ADR D5) — the bot tag reaches the generated client order id."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    InvalidClientOrderTagError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.orders.test_preview_order import (
    _handler,
)


def test_a_tagged_request_previews_an_order_with_a_tagged_id() -> None:
    """`EPIC-029A` (ADR D5): the tag reaches the generator through the preview."""
    preview = _handler().execute(
        PreviewOrderQuery(
            venue=TradingVenue.FUTURES_TESTNET,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.0137"),
            reference_price=Decimal(64000),
            client_order_tag="a3f9c1",
        )
    )
    assert preview.order.client_order_id.startswith("SEW-a3f9c1-")


def test_a_malformed_tag_never_builds_a_query() -> None:
    with pytest.raises(InvalidClientOrderTagError):
        PreviewOrderQuery(
            venue=TradingVenue.FUTURES_TESTNET,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal(1),
            reference_price=Decimal(64000),
            client_order_tag="BAD",
        )

"""`EPIC-028H` — the confirmation names what will be sent: the rounded
order, its total and fee, and any rounding the typed amount went through;
`EPIC-028O` adds a stop-limit's stop and a quote-sized buy's spend."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_confirmation import (
    build_confirmation,
)

_PREVIEW = OrderPreview(
    order=Order(
        client_order_id=generate_client_order_id(),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.0120"),
        price=Decimal("60000.00"),
    ),
    raw_quantity=Decimal("0.0120"),
    estimated_notional=Decimal(720),
    min_notional=Decimal(5),
    step_size=Decimal("0.0001"),
    notional_check=NotionalCheck.SUFFICIENT,
)


def _confirm(preview: OrderPreview, price: str = "60000.00"):
    return build_confirmation(
        preview,
        side_label="Buy",
        venue_label="Spot Testnet",
        base_asset="BTC",
        quote_asset="USDT",
        price=Decimal(price),
        fee_rate=Decimal("0.001"),
    )


def test_a_limit_order_names_its_amount_price_total_and_fee() -> None:
    confirmation = _confirm(_PREVIEW)

    assert confirmation.title == "Place Buy order"
    assert confirmation.question == (
        "Buy 0.0120 BTC at 60,000.00 USDT, as a limit order on Spot Testnet?"
    )
    assert "Total: 720.00 USDT" in confirmation.details
    assert "Estimated fee: 0.72 USDT" in confirmation.details
    assert "rounded" not in confirmation.details


def test_a_market_order_says_its_price_is_approximate() -> None:
    market = replace(
        _PREVIEW, order=replace(_PREVIEW.order, order_type=OrderType.MARKET, price=None)
    )

    confirmation = _confirm(market, "60123.45")

    assert "at about 60,123.45 USDT, as a market order" in confirmation.question
    assert "Total: about " in confirmation.details


def test_a_rounded_amount_is_said() -> None:
    rounded = replace(_PREVIEW, raw_quantity=Decimal("0.01239"))

    confirmation = _confirm(rounded)

    assert "rounded down from 0.01239 to the lot step of 0.0001" in (
        confirmation.details
    )


def test_a_stop_limit_names_its_stop() -> None:
    stop = replace(
        _PREVIEW,
        order=replace(
            _PREVIEW.order,
            order_type=OrderType.STOP_LIMIT,
            stop_price=Decimal("59900.00"),
        ),
    )

    confirmation = _confirm(stop)

    assert confirmation.question == (
        "Buy 0.0120 BTC at 60,000.00 USDT once the price reaches 59,900.00 USDT, as a "
        "stop-limit order on Spot Testnet?"
    )
    assert "only when the last price reaches 59,900.00 USDT" in confirmation.details


def test_a_quote_sized_buy_names_what_it_spends() -> None:
    quote = replace(
        _PREVIEW,
        order=replace(
            _PREVIEW.order,
            order_type=OrderType.MARKET,
            price=None,
            quantity=Decimal("0.0041"),
            quote_quantity=Decimal(250),
        ),
        raw_quantity=Decimal("0.004166"),
    )

    confirmation = _confirm(quote, "60000")

    assert confirmation.question == (
        "Spend 250.00 USDT to buy BTC, as a market order on Spot Testnet?"
    )
    assert "Spend: 250.00 USDT" in confirmation.details
    assert "Estimated amount: about 0.0041 BTC" in confirmation.details
    assert "Estimated fee: 0.25 USDT" in confirmation.details
    # The exchange sizes it from the quote, so no lot rounding is claimed.
    assert "rounded" not in confirmation.details


def test_a_price_finer_than_its_band_is_shown_exactly() -> None:
    """The order carries the price exactly, so the question shows every
    decimal of it, never fewer than two (review of PR #389)."""
    fine = replace(
        _PREVIEW,
        order=replace(_PREVIEW.order, price=Decimal("1500.123")),
    )

    confirmation = _confirm(fine, "1500.123")

    assert "at 1,500.123 USDT" in confirmation.question

"""`EPIC-028O` — the value types the new reads answer with refuse a figure no
exchange would send, and `LeverageBrackets` finds a notional's bracket at the
boundaries Binance uses (floor inclusive, cap exclusive)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import (
    MarkPrice,
)


def _bracket(
    number: int, leverage: int, floor: int, cap: int, rate: str = "0.004"
) -> LeverageBracket:
    return LeverageBracket(
        bracket=number,
        initial_leverage=leverage,
        notional_floor=Decimal(floor),
        notional_cap=Decimal(cap),
        maintenance_margin_rate=Decimal(rate),
        maintenance_amount=Decimal(0),
    )


_TABLE = LeverageBrackets(
    "BTCUSDT",
    (
        _bracket(1, 125, 0, 50_000),
        _bracket(2, 100, 50_000, 500_000, "0.005"),
        _bracket(3, 50, 500_000, 2_000_000, "0.01"),
    ),
)


@pytest.mark.parametrize(
    ("notional", "bracket"),
    [
        (Decimal(0), 1),
        (Decimal("49999.99"), 1),
        (Decimal(50_000), 2),
        (Decimal("499999.99"), 2),
        (Decimal(500_000), 3),
        (Decimal(2_000_000), 3),
        (Decimal(9_000_000), 3),
    ],
    ids=[
        "zero",
        "below-first-cap",
        "at-first-cap",
        "below-second-cap",
        "at-second-cap",
        "at-last-cap",
        "past-last-cap",
    ],
)
def test_a_notional_falls_in_the_bracket_whose_band_holds_it(
    notional: Decimal, bracket: int
) -> None:
    assert _TABLE.bracket_for(notional).bracket == bracket


def test_the_highest_leverage_is_the_first_brackets() -> None:
    assert _TABLE.max_leverage == 125


def test_a_negative_notional_has_no_bracket() -> None:
    with pytest.raises(ValueError, match="notional"):
        _TABLE.bracket_for(Decimal(-1))


def test_brackets_with_a_gap_are_refused() -> None:
    with pytest.raises(ValueError, match="previous cap"):
        LeverageBrackets(
            "BTCUSDT",
            (_bracket(1, 125, 0, 50_000), _bracket(2, 100, 60_000, 500_000)),
        )


def test_a_symbol_with_no_brackets_is_refused() -> None:
    with pytest.raises(ValueError, match="no leverage brackets"):
        LeverageBrackets("BTCUSDT", ())


@pytest.mark.parametrize(
    ("leverage", "floor", "cap", "message"),
    [
        (0, 0, 50_000, "initial_leverage"),
        (125, 50_000, 50_000, "not above floor"),
        (125, -1, 50_000, "notional_floor"),
    ],
    ids=["no-leverage", "empty-band", "negative-floor"],
)
def test_a_bracket_no_exchange_would_send_is_refused(
    leverage: int, floor: int, cap: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _bracket(1, leverage, floor, cap)


def test_a_setting_below_one_times_is_refused() -> None:
    with pytest.raises(ValueError, match="leverage"):
        FuturesSymbolSetting("BTCUSDT", 0, MarginType.CROSSED, Decimal(1))


def test_a_mark_price_of_zero_is_refused() -> None:
    with pytest.raises(ValueError, match="mark_price"):
        MarkPrice("BTCUSDT", Decimal(0), datetime(2026, 10, 1, tzinfo=UTC))


@pytest.mark.parametrize(
    ("bid", "bid_qty", "ask", "ask_qty", "has_bid", "has_ask"),
    [
        ("100", "1", "101", "1", True, True),
        ("0", "0", "101", "1", False, True),
        ("100", "1", "0", "0", True, False),
        ("100", "0", "101", "0", False, False),
    ],
    ids=["both-sides", "no-bid", "no-ask", "prices-without-quantity"],
)
def test_a_side_counts_only_with_a_price_and_a_quantity(
    bid: str, bid_qty: str, ask: str, ask_qty: str, has_bid: bool, has_ask: bool
) -> None:
    book = BestBidAsk(
        "BTCUSDT", Decimal(bid), Decimal(bid_qty), Decimal(ask), Decimal(ask_qty)
    )

    assert (book.has_bid, book.has_ask) == (has_bid, has_ask)


def test_a_negative_book_figure_is_refused() -> None:
    with pytest.raises(ValueError, match="ask_quantity"):
        BestBidAsk("BTCUSDT", Decimal(1), Decimal(1), Decimal(2), Decimal(-1))

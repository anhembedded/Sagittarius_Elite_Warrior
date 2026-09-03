"""`EPIC-021H` — parses Binance Futures User Data Stream payloads. Fixtures
below match Binance's own documented `ORDER_TRADE_UPDATE`/`ACCOUNT_UPDATE`
shapes (short single-letter keys nested under `"o"`/`"a"`), not the REST
response shape `futures_order_payload_mapper.py` parses."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.trading.time_in_force import TimeInForce
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.infrastructure.binance.user_data_event_parser import (
    account_update_captured_at,
    account_update_changed_symbols,
    account_update_position_pnls,
    account_update_wallet_balance,
    fill_details,
    is_fill_execution,
    parse_order_trade_update,
)


def _order_trade_update(**overrides: object) -> dict:
    o = {
        "s": "BTCUSDT",
        "c": "SEW-a91f4c72e0b8",
        "S": "BUY",
        "o": "MARKET",
        "f": "GTC",
        "q": "0.002",
        "p": "0",
        "ap": "64105.10",
        "sp": "0",
        "x": "TRADE",
        "X": "PARTIALLY_FILLED",
        "i": 8886774,
        "l": "0.001",
        "z": "0.001",
        "L": "64105.10",
        "N": "USDT",
        "n": "0.0013",
        "T": 1591274595163,
        "t": 1234,
        "rp": "0",
    }
    o.update(overrides)
    return {"e": "ORDER_TRADE_UPDATE", "T": 1591274595163, "E": 1591274595163, "o": o}


class TestParseOrderTradeUpdate:
    def test_parses_a_partial_fill(self) -> None:
        """The exact case backtest never produces (`EPIC-021H` §5's own
        worked example) — the whole reason this task exists."""
        order = parse_order_trade_update(_order_trade_update())

        assert str(order.client_order_id) == "SEW-a91f4c72e0b8"
        assert order.symbol == "BTCUSDT"
        assert order.side is OrderSide.BUY
        assert order.order_type is OrderType.MARKET
        assert order.status is OrderStatus.PARTIALLY_FILLED
        assert order.quantity == Decimal("0.002")

    def test_parses_a_full_fill(self) -> None:
        order = parse_order_trade_update(
            _order_trade_update(X="FILLED", z="0.002", l="0.001")
        )
        assert order.status is OrderStatus.FILLED

    def test_parses_a_new_acknowledgement(self) -> None:
        order = parse_order_trade_update(
            _order_trade_update(X="NEW", x="NEW", z="0", l="0")
        )
        assert order.status is OrderStatus.NEW

    def test_limit_order_carries_price_and_time_in_force(self) -> None:
        order = parse_order_trade_update(
            _order_trade_update(o="LIMIT", p="64000.00", f="GTC")
        )
        assert order.order_type is OrderType.LIMIT
        assert order.price == Decimal("64000.00")
        assert order.time_in_force is TimeInForce.GTC

    def test_market_order_has_no_price(self) -> None:
        order = parse_order_trade_update(_order_trade_update())
        assert order.price is None

    def test_an_unrecognized_status_falls_back_to_unknown_not_a_raise(self) -> None:
        """`BUG-091` — before this fix, an exchange status this app's
        deliberately-narrow `OrderStatus` has no member for (e.g. an
        exchange-internal status on an order this app did not place
        itself) raised `KeyError` and the whole `ORDER_TRADE_UPDATE` was
        dropped — the order stayed stuck at whatever stale status this app
        last knew, forever."""
        order = parse_order_trade_update(_order_trade_update(X="EXPIRED_IN_MATCH"))
        assert order.status is OrderStatus.UNKNOWN
        # Every other field still parses — only the unrecognized one falls
        # back, nothing else is lost.
        assert str(order.client_order_id) == "SEW-a91f4c72e0b8"
        assert order.quantity == Decimal("0.002")

    def test_an_unrecognized_order_type_falls_back_to_unknown_not_a_raise(self) -> None:
        order = parse_order_trade_update(_order_trade_update(o="TRAILING_STOP_MARKET"))
        assert order.order_type is OrderType.UNKNOWN

    def test_an_unrecognized_time_in_force_falls_back_to_none_not_a_raise(
        self,
    ) -> None:
        order = parse_order_trade_update(_order_trade_update(f="GTX"))
        assert order.time_in_force is None


class TestIsFillExecution:
    def test_trade_execution_type_is_a_fill(self) -> None:
        assert is_fill_execution(_order_trade_update(x="TRADE"))

    def test_new_execution_type_is_not_a_fill(self) -> None:
        assert not is_fill_execution(_order_trade_update(x="NEW"))

    def test_canceled_execution_type_is_not_a_fill(self) -> None:
        assert not is_fill_execution(_order_trade_update(x="CANCELED"))


class TestFillDetails:
    def test_returns_last_fill_price_and_quantity_not_running_totals(self) -> None:
        """`"L"`/`"l"` (this fill) must be read, not `"ap"`/`"z"` (running
        average price / accumulated quantity) — using the wrong pair would
        silently report the order's cumulative fill as if it were this
        one event's fill."""
        price, quantity = fill_details(
            _order_trade_update(L="64105.10", l="0.001", ap="64100.00", z="0.0015")
        )
        assert price == Decimal("64105.10")
        assert quantity == Decimal("0.001")

    def test_raises_on_a_non_fill_payload_missing_fill_fields(self) -> None:
        payload = _order_trade_update(x="NEW")
        del payload["o"]["L"]
        del payload["o"]["l"]
        with pytest.raises(KeyError):
            fill_details(payload)


class TestAccountUpdateChangedSymbols:
    def test_returns_every_symbol_including_one_that_went_flat(self) -> None:
        payload = {
            "e": "ACCOUNT_UPDATE",
            "T": 1564745798939,
            "E": 1564745798939,
            "a": {
                "m": "ORDER",
                "B": [{"a": "USDT", "wb": "122624.12", "cw": "100.12"}],
                "P": [
                    {
                        "s": "BTCUSDT",
                        "pa": "0.002",
                        "ep": "64105.35",
                        "cr": "0",
                        "up": "-0.02",
                        "mt": "cross",
                        "iw": "0",
                        "ps": "BOTH",
                    },
                    {
                        "s": "ETHUSDT",
                        "pa": "0",
                        "ep": "0",
                        "cr": "0",
                        "up": "0",
                        "mt": "cross",
                        "iw": "0",
                        "ps": "BOTH",
                    },
                ],
            },
        }
        assert account_update_changed_symbols(payload) == ["BTCUSDT", "ETHUSDT"]

    def test_no_position_section_returns_empty_list(self) -> None:
        payload = {
            "e": "ACCOUNT_UPDATE",
            "T": 1,
            "E": 1,
            "a": {"m": "ORDER", "B": [], "P": []},
        }
        assert account_update_changed_symbols(payload) == []


class TestAccountUpdatePositionPnls:
    """`EPIC-021M` §2.1, `BUG-092`."""

    def test_reads_unrealized_pnl_per_symbol_for_this_event_only(self) -> None:
        """`BUG-092` — this function must return only what *this* message
        reports, not a full-account snapshot: `FuturesUserDataStream` is
        the one responsible for folding it into a running total across
        events (`test_futures_user_data_stream.py` covers that)."""
        payload = {
            "e": "ACCOUNT_UPDATE",
            "T": 1564745798939,
            "E": 1564745798939,
            "a": {
                "m": "ORDER",
                "B": [{"a": "USDT", "wb": "122624.12", "cw": "100.12"}],
                "P": [
                    {"s": "BTCUSDT", "pa": "0.002", "up": "-0.02"},
                    {"s": "ETHUSDT", "pa": "1.5", "up": "3.75"},
                ],
            },
        }

        assert account_update_position_pnls(payload) == {
            "BTCUSDT": Decimal("-0.02"),
            "ETHUSDT": Decimal("3.75"),
        }

    def test_no_positions_section_returns_an_empty_dict(self) -> None:
        payload = {
            "e": "ACCOUNT_UPDATE",
            "T": 1,
            "E": 1,
            "a": {"m": "ORDER", "B": [{"a": "USDT", "wb": "100.00", "cw": "100.00"}]},
        }

        assert account_update_position_pnls(payload) == {}


class TestAccountUpdateWalletBalance:
    def test_reads_the_quote_asset_balance(self) -> None:
        payload = {
            "e": "ACCOUNT_UPDATE",
            "T": 1,
            "E": 1,
            "a": {"m": "ORDER", "B": [{"a": "USDT", "wb": "500.00", "cw": "500.00"}]},
        }

        assert account_update_wallet_balance(payload) == Decimal("500.00")

    def test_ignores_balances_for_assets_other_than_the_quote_asset(self) -> None:
        payload = {
            "e": "ACCOUNT_UPDATE",
            "T": 1,
            "E": 1,
            "a": {
                "m": "ORDER",
                "B": [
                    {"a": "BUSD", "wb": "999.00", "cw": "999.00"},
                    {"a": "USDT", "wb": "500.00", "cw": "500.00"},
                ],
                "P": [],
            },
        }

        assert account_update_wallet_balance(payload) == Decimal("500.00")

    def test_no_matching_balance_entry_returns_none_not_a_garbage_zero(self) -> None:
        payload = {
            "e": "ACCOUNT_UPDATE",
            "T": 1,
            "E": 1,
            "a": {"m": "ORDER", "B": [], "P": []},
        }

        assert account_update_wallet_balance(payload) is None


class TestAccountUpdateCapturedAt:
    def test_reads_the_streams_own_event_time(self) -> None:
        payload = {"e": "ACCOUNT_UPDATE", "T": 1, "E": 1564745798939, "a": {}}

        assert account_update_captured_at(payload) == datetime.fromtimestamp(
            1564745798.939, tz=UTC
        )

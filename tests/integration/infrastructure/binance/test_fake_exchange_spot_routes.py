"""`EPIC-027J` — the fake exchange's new Spot signed routes, exercised
through a real `binance.client.Client` the same way
`test_session_factories_against_fake_server.py` already exercises the
existing Futures ones.

@details `EPIC-027K` (the real Spot `ITradingClient` adapter) does not
exist yet, so there is no application-level adapter to drive these routes
through. The test-substitution rule (`testing-rule.md` §2: replace only at
the network boundary, never a hand-written port double) is satisfied here
by using `python-binance`'s own real `Client` methods directly against the
fake — proving the fixture itself answers Binance's real shapes, exactly
the precedent `test_session_factories_against_fake_server.py` set for
`MarketDataSessionFactory`/`FuturesSessionFactory`.

`_Handler`/`spot_account` are reached directly (not through the public
`FakeServerUrls` entry point) only to drain queued user-data events — there
is no live WebSocket push in this HTTP-only fixture, so a test proving a
fill queued the right event has nowhere else to look. This is a white-box
test of the fixture's own internals, the same category as
`OrderBookState`'s own direct exercise elsewhere in this file.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from binance.client import Client
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.tests.sanity.fake_exchange.server import (
    _Handler,
    run_binance_fake_server,
)


def _spot_client() -> Client:
    return Client(api_key="k", api_secret="s", testnet=True)


def _patch_spot(urls):
    return patch.object(Client, "API_TESTNET_URL", urls.spot)


def _filter_of_type(symbol_info: dict, filter_type: str) -> dict:
    return next(f for f in symbol_info["filters"] if f["filterType"] == filter_type)


def test_exchange_info_reports_real_spot_shaped_filters():
    with run_binance_fake_server() as urls, _patch_spot(urls):
        info = _spot_client().get_symbol_info("BTCUSDT")

        assert info["baseAsset"] == "BTC"
        assert info["quoteAsset"] == "USDT"
        assert _filter_of_type(info, "NOTIONAL")["minNotional"] == "5.00000000"


def test_a_test_order_touches_no_balance():
    with run_binance_fake_server() as urls, _patch_spot(urls):
        client = _spot_client()
        before = {b["asset"]: b["free"] for b in client.get_account()["balances"]}

        response = client.create_test_order(
            symbol="BTCUSDT", side="BUY", type="MARKET", quantity="1"
        )

        after = {b["asset"]: b["free"] for b in client.get_account()["balances"]}
        assert response == {}
        assert after == before


def test_a_filled_market_buy_moves_quote_to_base_minus_fee_in_base():
    with run_binance_fake_server() as urls, _patch_spot(urls):
        client = _spot_client()
        before = {
            b["asset"]: float(b["free"]) for b in client.get_account()["balances"]
        }

        order = client.create_order(
            symbol="BTCUSDT", side="BUY", type="MARKET", quantity="1"
        )

        after = {b["asset"]: float(b["free"]) for b in client.get_account()["balances"]}
        assert order["status"] == "FILLED"
        assert after["USDT"] == before["USDT"] - 50000
        # received 1 BTC minus a 0.1% fee charged in the received asset (BTC)
        assert after["BTC"] == before["BTC"] + 1 - 0.001
        assert order["fills"][0]["commissionAsset"] == "BTC"


def test_a_filled_market_sell_moves_base_to_quote_minus_fee_in_quote():
    with run_binance_fake_server() as urls, _patch_spot(urls):
        client = _spot_client()
        before = {
            b["asset"]: float(b["free"]) for b in client.get_account()["balances"]
        }

        order = client.create_order(
            symbol="BTCUSDT", side="SELL", type="MARKET", quantity="1"
        )

        after = {b["asset"]: float(b["free"]) for b in client.get_account()["balances"]}
        assert order["status"] == "FILLED"
        assert after["BTC"] == before["BTC"] - 1
        # received 50000 USDT minus a 0.1% fee charged in the received asset (USDT)
        assert after["USDT"] == before["USDT"] + 50000 - 50
        assert order["fills"][0]["commissionAsset"] == "USDT"


def test_a_fill_queues_execution_report_and_account_position_events():
    with run_binance_fake_server() as urls, _patch_spot(urls):
        client = _spot_client()

        client.create_order(symbol="ETHUSDT", side="BUY", type="MARKET", quantity="2")

        events = _Handler.spot_account.drain_user_data_events()
        kinds = [event["e"] for event in events]
        assert kinds == ["executionReport", "outboundAccountPosition"]
        report = events[0]
        assert report["s"] == "ETHUSDT"
        assert report["S"] == "BUY"
        assert report["X"] == "FILLED"


def test_a_limit_order_stays_open_until_canceled():
    with run_binance_fake_server() as urls, _patch_spot(urls):
        client = _spot_client()

        placed = client.create_order(
            symbol="BTCUSDT",
            side="BUY",
            type="LIMIT",
            timeInForce="GTC",
            quantity="1",
            price="40000",
        )
        assert placed["status"] == "NEW"
        assert (
            client.get_open_orders(symbol="BTCUSDT")[0]["orderId"] == placed["orderId"]
        )

        canceled = client.cancel_order(
            symbol="BTCUSDT", origClientOrderId=placed["clientOrderId"]
        )

        assert canceled["status"] == "CANCELED"
        assert client.get_open_orders(symbol="BTCUSDT") == []


def test_canceling_an_unknown_order_answers_binances_real_error_shape():
    with run_binance_fake_server() as urls, _patch_spot(urls):
        client = _spot_client()

        with pytest.raises(BinanceAPIException) as excinfo:
            client.cancel_order(symbol="BTCUSDT", origClientOrderId="does-not-exist")
        assert excinfo.value.code == -2011


def test_cancel_all_open_orders_answers_a_list_of_canceled_orders():
    with run_binance_fake_server() as urls, _patch_spot(urls):
        client = _spot_client()
        client.create_order(
            symbol="BTCUSDT",
            side="BUY",
            type="LIMIT",
            timeInForce="GTC",
            quantity="1",
            price="40000",
        )

        canceled = client.cancel_all_open_orders(symbol="BTCUSDT")

        assert len(canceled) == 1
        assert canceled[0]["status"] == "CANCELED"
        assert client.get_open_orders(symbol="BTCUSDT") == []


def test_user_data_stream_listen_key_lifecycle_round_trips():
    with run_binance_fake_server() as urls, _patch_spot(urls):
        client = _spot_client()

        listen_key = client.stream_get_listen_key()
        client.stream_keepalive(listen_key)
        client.stream_close(listen_key)

        assert listen_key

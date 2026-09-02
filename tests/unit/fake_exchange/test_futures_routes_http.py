"""`EPIC-021J` §4 — the fake server's HTTP surface itself, bypassing
`python-binance` entirely: every new route responds with the right shape,
**and** an unrecognized path still 404s rather than a plausible-looking
empty success. Two-directional on purpose — a route table that only ever
gets tested for its happy path can't prove an unexpected call would be
loud.
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server

#: A local loopback fixture never needs more than this to answer — a hang
#: here would be this fixture's own bug, not a slow remote service.
_TIMEOUT = 5


def test_unknown_path_404s_on_every_verb() -> None:
    with run_binance_fake_server() as urls:
        assert (
            requests.get(f"{urls.futures}/v1/notARoute", timeout=_TIMEOUT).status_code
            == 404
        )
        assert (
            requests.post(f"{urls.futures}/v1/notARoute", timeout=_TIMEOUT).status_code
            == 404
        )
        assert (
            requests.put(f"{urls.futures}/v1/notARoute", timeout=_TIMEOUT).status_code
            == 404
        )
        assert (
            requests.delete(
                f"{urls.futures}/v1/notARoute", timeout=_TIMEOUT
            ).status_code
            == 404
        )
        assert (
            requests.get(f"{urls.spot}/v3/notARoute", timeout=_TIMEOUT).status_code
            == 404
        )


def test_order_lifecycle_over_raw_http() -> None:
    with run_binance_fake_server() as urls:
        base = f"{urls.futures}/v1"

        empty = requests.get(
            f"{base}/openOrders", params={"symbol": "BTCUSDT"}, timeout=_TIMEOUT
        )
        assert empty.status_code == 200
        assert empty.json() == []

        placed = requests.post(
            f"{base}/order",
            data={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "MARKET",
                "quantity": "0.002",
                "newClientOrderId": "SEW-httptest01",
            },
            timeout=_TIMEOUT,
        )
        assert placed.status_code == 200
        assert placed.json()["status"] == "NEW"

        after_place = requests.get(
            f"{base}/openOrders", params={"symbol": "BTCUSDT"}, timeout=_TIMEOUT
        )
        assert [o["clientOrderId"] for o in after_place.json()] == ["SEW-httptest01"]

        canceled = requests.delete(
            f"{base}/order",
            data={"symbol": "BTCUSDT", "origClientOrderId": "SEW-httptest01"},
            timeout=_TIMEOUT,
        )
        assert canceled.status_code == 200
        assert canceled.json()["status"] == "CANCELED"

        after_cancel = requests.get(
            f"{base}/openOrders", params={"symbol": "BTCUSDT"}, timeout=_TIMEOUT
        )
        assert after_cancel.json() == []


def test_cancel_unknown_order_returns_400_with_binances_real_shape() -> None:
    with run_binance_fake_server() as urls:
        response = requests.delete(
            f"{urls.futures}/v1/order",
            data={"symbol": "BTCUSDT", "origClientOrderId": "SEW-neverPlaced"},
            timeout=_TIMEOUT,
        )

        assert response.status_code == 400
        assert response.json() == {"code": -2011, "msg": "Unknown order sent."}


def test_cancel_all_open_orders_returns_the_acknowledgement_shape() -> None:
    with run_binance_fake_server() as urls:
        response = requests.delete(
            f"{urls.futures}/v1/allOpenOrders",
            data={"symbol": "BTCUSDT"},
            timeout=_TIMEOUT,
        )

        assert response.status_code == 200
        assert response.json()["code"] == 200


def test_order_test_endpoint_never_creates_open_order_state() -> None:
    """`VALIDATE_ONLY` mode (`EPIC-021F`) must never leak into
    `openOrders` — that would make a dry-run indistinguishable from a
    real submission."""
    with run_binance_fake_server() as urls:
        base = f"{urls.futures}/v1"

        response = requests.post(
            f"{base}/order/test",
            data={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "MARKET",
                "quantity": "0.002",
                "newClientOrderId": "SEW-dryrun01",
            },
            timeout=_TIMEOUT,
        )

        assert response.status_code == 200
        assert response.json() == {}
        assert requests.get(f"{base}/openOrders", timeout=_TIMEOUT).json() == []


def test_listen_key_lifecycle() -> None:
    with run_binance_fake_server() as urls:
        base = f"{urls.futures}/v1"

        created = requests.post(f"{base}/listenKey", timeout=_TIMEOUT)
        assert created.status_code == 200
        assert created.json()["listenKey"]

        renewed = requests.put(
            f"{base}/listenKey",
            data={"listenKey": created.json()["listenKey"]},
            timeout=_TIMEOUT,
        )
        assert renewed.status_code == 200


def test_position_risk_is_always_an_empty_list() -> None:
    with run_binance_fake_server() as urls:
        response = requests.get(f"{urls.futures}/v3/positionRisk", timeout=_TIMEOUT)

        assert response.status_code == 200
        assert response.json() == []

"""`EPIC-035D` — the fake exchange can answer wrongly on request: a queued fault
is used once, by the first request it matches, and a request it does not match is
served as before. The resilience tests rest on it, so it is proven over raw HTTP."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sanity"))
from binance_fake_server import run_binance_fake_server
from fake_exchange.server import FaultAnswer


def test_a_queued_fault_answers_once_with_its_status_and_headers() -> None:
    with run_binance_fake_server() as urls:
        urls.faults.queued.append(
            FaultAnswer(
                "/v3/time",
                status=429,
                body={"code": -1003, "msg": "Too many requests."},
                headers={"Retry-After": "7"},
            )
        )

        first = requests.get(f"{urls.spot}/v3/time", timeout=5)
        second = requests.get(f"{urls.spot}/v3/time", timeout=5)

    assert (first.status_code, first.headers["Retry-After"]) == (429, "7")
    assert first.json()["code"] == -1003
    assert second.status_code == 200
    assert urls.faults.queued == []


def test_a_fault_waits_for_the_request_it_matches() -> None:
    with run_binance_fake_server() as urls:
        urls.faults.queued.append(FaultAnswer("/v3/order", status=503, body="busy"))

        unmatched = requests.get(f"{urls.spot}/v3/time", timeout=5)

    assert unmatched.status_code == 200
    assert len(urls.faults.queued) == 1


def test_a_dropped_request_gets_no_answer() -> None:
    with run_binance_fake_server() as urls:
        urls.faults.queued.append(FaultAnswer("/v3/time", drop=True))

        with pytest.raises(requests.exceptions.ConnectionError):
            requests.get(f"{urls.spot}/v3/time", timeout=5)
        after = requests.get(f"{urls.spot}/v3/time", timeout=5)

    assert after.status_code == 200


def test_the_spot_lookup_of_an_order_the_exchange_never_saw_is_binances_2013() -> None:
    with run_binance_fake_server() as urls:
        answer = requests.get(
            f"{urls.spot}/v3/order",
            params={"symbol": "BTCUSDT", "origClientOrderId": "SEW-never"},
            timeout=5,
        )

    assert (answer.status_code, answer.json()["code"]) == (400, -2013)

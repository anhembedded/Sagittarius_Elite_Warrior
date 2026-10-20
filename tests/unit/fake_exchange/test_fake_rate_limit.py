"""`EPIC-037E` — the fake exchange refuses past its weight limit as Binance does: 429 with the
`-1003` body and a `Retry-After`, then 418 for a client that carries on inside the window.
Sources: `rate_limit_policy.py`. Off by default (`BUG-216`'s journeys never reach the limit).
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server
from fake_exchange.history_log import now_ms

_TIMEOUT = 5
#: Fifty seconds into a minute, held still so the window cannot roll over mid-test.
_CLOCK = 1_000_000_010.0
_ACCOUNT_WEIGHT = 5


def test_a_request_past_the_limit_is_429_and_one_after_it_is_418() -> None:
    with run_binance_fake_server() as urls:
        urls.weights.use_clock(lambda: _CLOCK)
        urls.rate_limit.limit = _ACCOUNT_WEIGHT
        read = lambda: requests.get(f"{urls.futures}/v1/ping", timeout=_TIMEOUT)
        account = lambda: requests.get(f"{urls.futures}/v2/account", timeout=_TIMEOUT)

        within = account()
        limited = read()
        banned = read()

    assert within.status_code == 200
    assert limited.status_code == 429
    assert limited.json()["code"] == -1003
    assert limited.headers["Retry-After"] == "10", "the seconds left in the minute"
    assert banned.status_code == 418
    assert banned.headers["Retry-After"] == "120"
    assert (urls.rate_limit.limited, urls.rate_limit.banned) == (1, 1)


def test_a_ban_is_held_for_its_retry_after_and_then_lifted() -> None:
    """The 418 names 120 s; a client that comes back inside them, even in a later minute, is still
    refused, and one that waits them out is served (`rate_limit_policy.py`)."""
    now = [_CLOCK]
    with run_binance_fake_server() as urls:
        urls.weights.use_clock(lambda: now[0])
        urls.rate_limit.limit = 1
        statuses = []
        for step in (
            0,
            0,
            0,
            15,
            100,
            190,
        ):  # then probes inside the 120 s, then one after them in a minute of its own
            now[0] = _CLOCK + step
            statuses.append(
                requests.get(f"{urls.futures}/v1/ping", timeout=_TIMEOUT).status_code
            )

    assert statuses == [200, 429, 418, 418, 418, 200]


def test_the_next_minute_is_served_again() -> None:
    now = [_CLOCK]
    with run_binance_fake_server() as urls:
        urls.weights.use_clock(lambda: now[0])
        urls.rate_limit.limit = 1
        requests.get(f"{urls.futures}/v1/ping", timeout=_TIMEOUT)
        assert (
            requests.get(f"{urls.futures}/v1/ping", timeout=_TIMEOUT).status_code == 429
        )

        now[0] += 60
        after = requests.get(f"{urls.futures}/v1/ping", timeout=_TIMEOUT)

    assert after.status_code == 200


def test_there_is_no_limit_unless_a_test_sets_one() -> None:
    with run_binance_fake_server() as urls:
        statuses = {
            requests.get(f"{urls.futures}/v2/account", timeout=_TIMEOUT).status_code
            for _ in range(5)
        }

    assert statuses == {200}


def test_a_signed_request_outside_the_receive_window_is_refused_without_asking() -> (
    None
):
    """`EPIC-037E` — `-1021` is on by default (`ClockPolicy`, `BUG-221`), not per test."""
    with run_binance_fake_server() as urls:
        stale_ms = 6_000  # past the 5 000 ms `recvWindow` (PR 615)
        answer = requests.get(
            f"{urls.futures}/v2/account",
            params={"timestamp": str(now_ms() - stale_ms), "signature": "x"},
            timeout=_TIMEOUT,
        )

    assert (answer.status_code, answer.json()["code"]) == (400, -1021)

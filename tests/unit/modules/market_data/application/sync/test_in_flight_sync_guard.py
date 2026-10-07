"""Tests for InFlightSyncGuard (BOT-121).

Deliberately uses REAL threads for the concurrency assertion, not a mocked
sequence of calls — a purely sequential test would pass by construction
regardless of whether the lock actually works, same trap
`test_exclusive_action.py` (the sibling primitive this one is NOT built on
top of, see the module docstring on `InFlightSyncGuard` for why) guards
against.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.in_flight_sync_guard import (
    InFlightSyncGuard,
)

SCOPE = "mainnet_public/spot"


def test_try_acquire_reserves_a_free_key():
    guard = InFlightSyncGuard()

    assert guard.try_acquire(SCOPE, "BTCUSDT", "1m") is True


def test_try_acquire_rejects_the_same_key_while_held():
    guard = InFlightSyncGuard()
    guard.try_acquire(SCOPE, "BTCUSDT", "1m")

    assert guard.try_acquire(SCOPE, "BTCUSDT", "1m") is False


def test_try_acquire_accepts_a_different_symbol_while_another_is_held():
    """Unlike ExclusiveAction, different keys must NOT exclude each other —
    bulk sync relies on distinct (symbol, interval) targets running
    concurrently on a thread pool."""
    guard = InFlightSyncGuard()
    guard.try_acquire(SCOPE, "BTCUSDT", "1m")

    assert guard.try_acquire(SCOPE, "ETHUSDT", "1m") is True


def test_try_acquire_accepts_a_different_interval_of_the_same_symbol_while_held():
    guard = InFlightSyncGuard()
    guard.try_acquire(SCOPE, "BTCUSDT", "1m")

    assert guard.try_acquire(SCOPE, "BTCUSDT", "1h") is True


def test_release_frees_the_key_for_a_later_acquire():
    guard = InFlightSyncGuard()
    guard.try_acquire(SCOPE, "BTCUSDT", "1m")

    guard.release(SCOPE, "BTCUSDT", "1m")

    assert guard.try_acquire(SCOPE, "BTCUSDT", "1m") is True


def test_release_of_a_key_never_held_is_a_no_op():
    guard = InFlightSyncGuard()

    guard.release(SCOPE, "BTCUSDT", "1m")  # must not raise

    assert guard.try_acquire(SCOPE, "BTCUSDT", "1m") is True


def test_many_real_concurrent_acquires_for_the_same_key_only_one_ever_wins():
    """The actual race BOT-121 guards against: Backtest's coverage-gap sync
    and a Data Management sync landing on the same (symbol, interval) at
    close to the same instant — only one may ever hold the key at once."""
    guard = InFlightSyncGuard()
    accepted = 0
    lock = threading.Lock()
    ready = threading.Barrier(8)

    def attempt() -> None:
        nonlocal accepted
        ready.wait(timeout=5)
        if guard.try_acquire(SCOPE, "BTCUSDT", "1m"):
            with lock:
                accepted += 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(attempt) for _ in range(8)]
        for future in futures:
            future.result(timeout=5)

    assert accepted == 1


def test_concurrent_acquires_for_distinct_keys_all_win():
    guard = InFlightSyncGuard()
    symbols = [f"SYM{i}USDT" for i in range(8)]
    results: list[bool] = []
    lock = threading.Lock()
    ready = threading.Barrier(8)

    def attempt(symbol: str) -> None:
        ready.wait(timeout=5)
        result = guard.try_acquire(SCOPE, symbol, "1m")
        with lock:
            results.append(result)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(attempt, symbol) for symbol in symbols]
        for future in futures:
            future.result(timeout=5)

    assert results == [True] * 8


def test_the_same_symbol_on_another_venue_or_market_is_another_key():
    """`BUG-172` — a Spot Testnet and a Spot Mainnet desk open on `BTCUSDT 1m`
    together fetch two series from two exchanges into two stores."""
    guard = InFlightSyncGuard()
    guard.try_acquire("mainnet_public/spot", "BTCUSDT", "1m")

    assert guard.try_acquire("spot_testnet/spot", "BTCUSDT", "1m") is True
    assert guard.try_acquire("mainnet_public/futures_usd_m", "BTCUSDT", "1m") is True
    assert guard.try_acquire("mainnet_public/spot", "BTCUSDT", "1m") is False

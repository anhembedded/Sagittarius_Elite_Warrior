"""`BOT-173` — the ledger that lets a trade be counted once.

@details Direct tests of what its docstring promises: one winner under
contention (the order pool and the websocket both report), a bound with
oldest-first eviction, a key scoped by symbol, and a claim that can be given
back when the fill could not be applied.
"""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.trading.application.reported_trades import (
    ReportedTrades,
)


def test_the_first_record_of_a_trade_wins_and_a_second_does_not() -> None:
    ledger = ReportedTrades()

    assert ledger.claim("BTCUSDT", 7) is True
    assert ledger.claim("BTCUSDT", 7) is False


def test_the_same_trade_id_on_another_symbol_is_another_trade() -> None:
    ledger = ReportedTrades()

    assert ledger.claim("BTCUSDT", 7) is True
    assert ledger.claim("ETHUSDT", 7) is True


def test_a_fill_without_a_trade_id_is_always_a_first_record() -> None:
    ledger = ReportedTrades()

    assert ledger.claim("BTCUSDT", None) is True
    assert ledger.claim("BTCUSDT", None) is True


def test_exactly_one_of_many_threads_claims_a_trade() -> None:
    ledger = ReportedTrades()
    threads = 16
    ids = range(300)
    wins: list[int] = []
    wins_lock = threading.Lock()
    start = threading.Barrier(threads)

    def work() -> None:
        start.wait()
        mine = [trade_id for trade_id in ids if ledger.claim("BTCUSDT", trade_id)]
        with wins_lock:
            wins.extend(mine)

    workers = [threading.Thread(target=work) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert sorted(wins) == list(ids)


def test_the_oldest_claim_is_forgotten_past_the_bound() -> None:
    ledger = ReportedTrades(limit=3)
    for trade_id in (1, 2, 3, 4):
        ledger.claim("BTCUSDT", trade_id)

    assert ledger.claim("BTCUSDT", 1) is True  # evicted, so a first record again
    assert ledger.claim("BTCUSDT", 4) is False  # still remembered


def test_the_ledger_never_holds_more_than_its_bound() -> None:
    ledger = ReportedTrades(limit=50)
    for trade_id in range(1_000):
        ledger.claim("BTCUSDT", trade_id)

    assert all(not ledger.claim("BTCUSDT", t) for t in range(950, 1_000))
    assert ledger.claim("BTCUSDT", 949) is True  # the 51st oldest is gone


def test_a_released_claim_can_be_made_again() -> None:
    ledger = ReportedTrades()
    ledger.claim("BTCUSDT", 7)

    ledger.release("BTCUSDT", 7)

    assert ledger.claim("BTCUSDT", 7) is True
    ledger.release("BTCUSDT", None)  # nothing to give back; not an error

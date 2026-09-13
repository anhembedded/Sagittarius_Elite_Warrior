"""
Golden master for the static backtest (HLD §9.2, ADR D18; Phase 3 gate in HLD
§6.3: "backtests bit-identical").

**Why.** `EPIC-025D` moves the whole backtest stack — `PaperExchange`, the
engine, the metrics, the out-of-sample split — into `modules/backtesting`
and deletes five dead use cases on the way. Every unit test in that tree
moves with it, so none of them can say whether the *sum* still behaves.
This test can: it runs one deterministic backtest through the public handler
and compares the complete result (every trade, the equity curve, every
metric, the out-of-sample split) with a recorded copy.

**What is recorded.** `backtest_golden_master.json` next to this file, written
once in Phase 0 and never edited by hand. If a change to the backtest is
*meant* to alter results, regenerate it in the same commit and say so in the
commit message:

    GOLDEN_MASTER_UPDATE=1 pytest tests/integration/golden -q

**Where the pieces live:** `dataset.py` (the seeded bars), `runner.py` (the
handler call), `serialisation.py` (result → JSON), `json_diff.py` (the
report), `fakes/` (the repository and publisher doubles).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.tests.integration.golden.dataset import (
    BAR_COUNT,
    make_golden_klines,
)
from Sagittarius_Elite_Warrior.tests.integration.golden.json_diff import diff
from Sagittarius_Elite_Warrior.tests.integration.golden.runner import (
    run_golden_backtest,
)
from Sagittarius_Elite_Warrior.tests.integration.golden.serialisation import serialise

_GOLDEN_FILE = Path(__file__).with_name("backtest_golden_master.json")
_UPDATE_ENV = "GOLDEN_MASTER_UPDATE"
#: Minimum round trips the dataset must produce, so the master exercises the
#: metrics with real trades rather than an empty list.
_MINIMUM_TRADES = 10
_MAX_DIFFERENCES_SHOWN = 40


def _bars_as_tuples() -> list[tuple[object, ...]]:
    return [
        (k.open_time, k.open_price, k.high_price, k.low_price, k.close_price, k.volume)
        for k in make_golden_klines()
    ]


def test_the_dataset_is_deterministic() -> None:
    first, second = _bars_as_tuples(), _bars_as_tuples()
    assert first == second
    assert len(first) == BAR_COUNT


def test_the_dataset_produces_a_meaningful_backtest() -> None:
    """The master is worthless if the strategy never trades on it — and a
    long-only strategy must never have produced a short (testing-rule §2)."""
    result = run_golden_backtest()
    assert len(result.trades) >= _MINIMUM_TRADES
    assert all(trade.side is PositionSide.LONG for trade in result.trades)
    assert result.out_of_sample is not None
    assert len(result.out_of_sample.in_sample.trades) >= 1
    assert len(result.out_of_sample.out_of_sample.trades) >= 1
    assert len(result.equity_curve) == BAR_COUNT


def test_static_backtest_matches_the_golden_master() -> None:
    actual = serialise(run_golden_backtest())
    if os.environ.get(_UPDATE_ENV) == "1":
        _GOLDEN_FILE.write_text(
            json.dumps(actual, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
    assert _GOLDEN_FILE.is_file(), (
        f"{_GOLDEN_FILE.name} is missing — run with {_UPDATE_ENV}=1 once and commit it"
    )
    expected = json.loads(_GOLDEN_FILE.read_text(encoding="utf-8"))
    differences = diff(expected, actual)
    overflow = len(differences) - _MAX_DIFFERENCES_SHOWN
    assert differences == [], (
        "the static backtest no longer reproduces the golden master.\n"
        "If the change is intended, regenerate the file in the same commit\n"
        f"({_UPDATE_ENV}=1) and say why in the commit message.\n\n"
        + "\n".join(differences[:_MAX_DIFFERENCES_SHOWN])
        + (f"\n  … {overflow} more" if overflow > 0 else "")
    )

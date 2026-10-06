"""`logic/run_texts.py`: the run's sentences write each figure as a table cell
does (`EPIC-033N`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.run_texts import (
    completed_event_text,
    progress_text,
    signal_text,
    sync_text,
)


def test_a_signal_names_its_price_as_a_price():
    assert signal_text("buy", "BTCUSDT", 64250.1) == "Signal: BUY BTCUSDT @ 64,250.10"
    assert signal_text("sell", "SHIBUSDT", 0.00001234).endswith("@ 0.00001234")


def test_a_completed_event_writes_its_count_and_duration():
    assert completed_event_text(1_200, 3_725.0) == (
        "Backtest completed: 1,200 trades (duration: 1:02:05)"
    )


def test_backtest_progress_writes_a_percent_and_an_eta_duration():
    assert progress_text("Testing in-sample", 42.0, 75) == (
        "Testing in-sample: 42.00% · ETA ~0:01:15"
    )
    # No ETA before the first bar completes.
    assert progress_text("Running", 0.0, None) == "Running: 0.00%"


def test_sync_progress_writes_counts_as_quantities_and_a_percent():
    assert sync_text(1_200, 5_000, 24.0) == "Syncing candles: 1,200/5,000 (24.00%)"

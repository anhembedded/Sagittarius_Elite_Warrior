"""`EPIC-040A` — what the Grid's Backtest page shows in each state, pinned at its public
surface before `EPIC-040D`/`040F` move it.

@details Each test drives the page the way a user does (`GridBacktest.follow`, a click on a
button) and reads what the user reads: the status words and which buttons are on. They reach
no private helper, so the same file runs unchanged against the workbench-hosted page. The
frames are the real page too (`preview_frames.py`), so these tests also say what the owner
sees in each frame."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QPushButton
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_view import (
    GridBacktestView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.preview_frames import (
    FRAMES,
    build_frame,
)


def _buttons(view: GridBacktestView) -> dict[str, bool]:
    """Each command the page offers, by its label: whether the user can click it now."""
    shown = {
        button.text(): button.isEnabled()
        for button in (
            view.run_button,
            view.cancel_button,
            view.sync_button,
            view.no_funding_button,
        )
        if button.isVisibleTo(view)
    }
    assert all(
        isinstance(b, QPushButton) for b in (view.run_button, view.cancel_button)
    )
    return shown


@pytest.fixture
def frame(qtbot):  # type: ignore[no-untyped-def]
    def build(name: str) -> GridBacktestView:
        view = build_frame(name)
        qtbot.addWidget(view)
        view.show()
        qtbot.waitExposed(view)
        return view

    yield build


def test_every_state_of_the_page_has_a_frame() -> None:
    assert set(FRAMES) == {
        "idle_no_bot",
        "idle_no_market_numbers",
        "idle_ready",
        "running",
        "syncing",
        "refused_candles",
        "refused_funding",
        "spot_result",
        "futures_result",
        "futures_liquidated",
        "cancelled",
        "another_bot",
    }


@pytest.mark.parametrize(
    ("name", "reason", "run_is_on"),
    [
        ("idle_no_bot", "Select a bot to backtest its parameters.", False),
        (
            "idle_no_market_numbers",
            "The market numbers for this symbol are still being read.",
            False,
        ),
        ("idle_ready", "", True),
    ],
)
def test_idle_says_why_run_is_off(
    frame, name: str, reason: str, run_is_on: bool
) -> None:  # type: ignore[no-untyped-def]
    view = frame(name)

    assert view.run_button.isEnabled() is run_is_on
    assert view.run_button.toolTip() == reason
    if reason:  # a ready page keeps its last status text (recorded in EPIC-040A)
        assert view.status.text() == reason
    assert _buttons(view) == {"Run backtest": run_is_on, "Cancel": False}
    assert view.summary_text() == {}


def test_running_offers_only_cancel_and_says_what_it_runs(frame) -> None:  # type: ignore[no-untyped-def]
    view = frame("running")

    assert view.status.text() == "Backtesting BTCUSDT on 15m…"
    assert _buttons(view) == {"Run backtest": False, "Cancel": True}
    assert view.summary_text() == {}


def test_a_sync_in_flight_is_stopped_not_cancelled(frame) -> None:  # type: ignore[no-untyped-def]
    view = frame("syncing")

    assert view.status.text().startswith(
        "Syncing BTCUSDT 15m candles and 1-second klines"
    )
    assert _buttons(view) == {"Run backtest": False, "Stop": True}


def test_missing_candles_offer_a_sync_and_keep_run_on(frame) -> None:  # type: ignore[no-untyped-def]
    view = frame("refused_candles")

    assert "No 15m candles of BTCUSDT" in view.status.text()
    assert _buttons(view) == {
        "Run backtest": True,
        "Cancel": False,
        "Sync candles": True,
    }
    assert view.summary_text() == {}


def test_missing_funding_offers_to_run_without_it_and_not_a_sync(frame) -> None:  # type: ignore[no-untyped-def]
    view = frame("refused_funding")

    assert "funding history of BTCUSDT could not be read" in view.status.text()
    assert _buttons(view) == {
        "Run backtest": True,
        "Cancel": False,
        "Run without funding": True,
    }


def test_a_spot_result_shows_its_figures_and_no_futures_line(frame) -> None:  # type: ignore[no-untyped-def]
    view = frame("spot_result")

    assert view.status.text() == "Backtest done."
    assert _buttons(view) == {"Run backtest": True, "Cancel": False}
    figures = view.summary_text()
    assert figures["candles"] == "120"
    assert "funding_paid" not in figures
    assert "Modelled" not in view.notes.text()
    assert view.equity.grid_curve.getData()[0] is not None


def test_a_futures_result_shows_funding_apart_and_says_it_is_modelled(frame) -> None:  # type: ignore[no-untyped-def]
    view = frame("futures_result")

    assert view.status.text() == "Backtest done."
    figures = view.summary_text()
    assert figures["funding_paid"] not in ("", "0.00")
    assert "Modelled, not replayed" in view.notes.text()
    assert "Stopped by a liquidation" not in view.notes.text()
    assert _buttons(view) == {"Run backtest": True, "Cancel": False}


def test_a_liquidated_result_names_the_liquidation_and_the_margin_lost(frame) -> None:  # type: ignore[no-untyped-def]
    view = frame("futures_liquidated")

    assert "Stopped by a liquidation" in view.notes.text()
    assert "forfeited" in view.notes.text()
    assert "funding_paid" in view.summary_text()


def test_cancel_leaves_the_last_result_and_says_so(frame) -> None:  # type: ignore[no-untyped-def]
    view = frame("cancelled")

    assert view.status.text() == "Backtest cancelled; the last result stays."
    assert _buttons(view) == {"Run backtest": True, "Cancel": False}
    assert view.summary_text()["candles"] == "120"


def test_another_bot_clears_the_result_and_the_run_is_on_again(frame) -> None:  # type: ignore[no-untyped-def]
    view = frame("another_bot")

    assert view.summary_text() == {}
    assert view.notes.text() == ""
    # Not pinned: the status line still reads "Backtest done." here, because
    # `show_idle("")` writes it only when there is a reason (recorded in EPIC-040A).
    assert _buttons(view) == {"Run backtest": True, "Cancel": False}

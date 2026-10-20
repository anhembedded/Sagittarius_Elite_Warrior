"""`EPIC-040D` — what the workbench does around a run: Futures funding and brackets, a period that
ends first, cancel, another bot, closing mid-run and a run that raised (the words of the states are in
`test_workbench_states.py`)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_kind_backtester import (
    outcome_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.funding_requirement import (
    FundingRequirement,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    bar,
    position_config,
    replay,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    schedule as funding_schedule,
)

from .workbench_fixtures import (
    WorkbenchWorld,
    build_workbench,
    futures_selection,
    selection,
)


@pytest.fixture
def world(qtbot: Any) -> Iterator[WorkbenchWorld]:
    built = build_workbench()
    qtbot.addWidget(built.workbench.page)
    yield built
    built.workbench.shutdown()


def _buttons(view: BacktestWorkbenchView) -> dict[str, bool]:
    """Each command the page offers, by its label: whether the person can click it now."""
    return {
        button.text(): button.isEnabled()
        for button in (
            view.run_button,
            view.cancel_button,
            view.sync_button,
            view.no_funding_button,
        )
        if button.isVisibleTo(view)
    }


def _run(world: WorkbenchWorld, qtbot: Any) -> None:
    qtbot.mouseClick(world.workbench.view.run_button, Qt.MouseButton.LeftButton)


def test_missing_funding_is_refused_first_and_only_a_click_runs_without_it(
    qtbot: Any,
) -> None:
    refusal = BacktestRefusal(
        "The funding history of BTCUSDT could not be read.", funding_unavailable=True
    )
    world = build_workbench(answers=(refusal, refusal))
    view = world.workbench.view
    qtbot.addWidget(view)
    world.workbench.follow(futures_selection())

    _run(world, qtbot)
    world.pool.run_all()

    assert "funding history of BTCUSDT" in view.status.text()
    assert _buttons(view) == {
        "Run backtest": True,
        "Cancel": False,
        "Run without funding": True,
    }
    assert world.dispatcher.queries[0].request.funding is FundingRequirement.REQUIRED
    assert len(world.dispatcher.queries) == 1

    qtbot.mouseClick(view.no_funding_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert [q.request.funding for q in world.dispatcher.queries] == [
        FundingRequirement.REQUIRED,
        FundingRequirement.OPTIONAL,
    ]
    world.workbench.shutdown()


def test_another_refusal_does_not_offer_to_skip_funding(qtbot: Any) -> None:
    world = build_workbench(answers=(BacktestRefusal("The period must hold candles."),))
    view = world.workbench.view
    qtbot.addWidget(view)
    world.workbench.follow(futures_selection())

    _run(world, qtbot)
    world.pool.run_all()

    assert not view.no_funding_button.isVisibleTo(view)
    world.workbench.shutdown()


def test_a_position_venue_waits_for_the_brackets_a_liquidation_price_needs(
    world: WorkbenchWorld,
) -> None:
    world.workbench.follow(futures_selection(risk=False))

    view = world.workbench.view
    assert not view.run_button.isEnabled()
    assert "leverage brackets" in view.run_button.toolTip()


def test_a_futures_result_shows_funding_apart_and_says_it_is_modelled(
    qtbot: Any,
) -> None:
    result = replay(
        [
            bar(0, "65000", "65200", "64800", "65000"),
            bar(1, "65000", "65100", "64900", "65050"),
        ],
        position_config("LONG", 3, stop_loss="percent:5"),
        funding_schedule(),
    )
    world = build_workbench(answers=(outcome_of(result),))
    view = world.workbench.view
    qtbot.addWidget(view)
    world.workbench.follow(futures_selection())

    _run(world, qtbot)
    world.pool.run_all()

    assert view.status.text() == "Backtest done."
    assert "funding_paid" in view.summary_text()
    assert "Modelled, not replayed" in view.notes.text()
    world.workbench.shutdown()


def test_a_period_that_ends_before_it_starts_is_refused_in_words(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    view.end.setDateTime(view.start.dateTime().addSecs(-3600))
    world.workbench.follow(selection())

    _run(world, qtbot)

    assert view.status.text() == "The period must end after it starts."
    assert world.dispatcher.queries == []
    assert not view.sync_button.isVisibleTo(view)


def test_cancel_publishes_nothing_and_the_last_result_stays(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection())
    _run(world, qtbot)
    world.pool.run_all()
    before = view.summary_text()

    _run(world, qtbot)
    qtbot.mouseClick(view.cancel_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert view.summary_text() == before
    assert view.status.text() == "Backtest cancelled; the last result stays."
    assert _buttons(view) == {"Run backtest": True, "Cancel": False}
    assert world.dispatcher.queries[-1].request.cancelled()


def test_another_bot_clears_the_result_and_says_the_new_states_words(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection("a3f9c1"))
    _run(world, qtbot)
    world.pool.run_all()
    assert view.summary_text()

    world.workbench.follow(selection("b7e2d4"))

    assert view.summary_text() == {} and view.notes.text() == ""
    assert view.equity.point_count() == 0 and view.fills_model.rowCount() == 0
    assert (
        view.status.text() == ""
    )  # not "Backtest done.": the page is ready for the new bot
    assert _buttons(view) == {"Run backtest": True, "Cancel": False}


def test_another_bot_mid_run_drops_the_late_answer_and_says_the_pages_own_state(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    """The Grid page kept "Backtesting…" with Run on and Cancel off (`EPIC-040A`)."""
    view = world.workbench.view
    world.workbench.follow(selection("a3f9c1"))
    _run(world, qtbot)

    world.workbench.follow(selection("b7e2d4"))
    world.pool.run_all()

    assert view.summary_text() == {} and view.notes.text() == ""
    assert view.status.text() == ""
    assert _buttons(view) == {"Run backtest": True, "Cancel": False}


def test_another_bot_mid_run_also_drops_a_late_refusal(qtbot: Any) -> None:
    world = build_workbench(answers=(BacktestRefusal("late", missing_candles=True),))
    view = world.workbench.view
    qtbot.addWidget(view)
    world.workbench.follow(selection("a3f9c1"))
    _run(world, qtbot)

    world.workbench.follow(selection("b7e2d4"))
    world.pool.run_all()

    assert view.status.text() == "" and not view.sync_button.isVisibleTo(view)
    world.workbench.shutdown()


def test_the_same_bot_re_read_keeps_its_run_and_result(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection())
    _run(world, qtbot)

    world.workbench.follow(selection())
    world.pool.run_all()

    assert view.status.text() == "Backtest done." and view.summary_text()


def test_closing_the_page_mid_run_drops_the_answer_without_an_error(
    qtbot: Any, caplog: pytest.LogCaptureFixture
) -> None:
    world = build_workbench()
    view = world.workbench.view
    world.workbench.follow(selection())
    _run(world, qtbot)

    world.workbench.shutdown()
    view.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    world.pool.run_all()

    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_a_backtest_that_raised_is_a_command_failure_not_the_page_text(
    qtbot: Any,
) -> None:
    """`BOT-169`: the page keeps a plain state line; the box says what to do and carries the
    exception only behind its Details."""
    world = build_workbench()
    view = world.workbench.view
    qtbot.addWidget(view)
    world.workbench.follow(selection())
    world.dispatcher.raises = ConnectionError("klines store unreachable")

    _run(world, qtbot)
    world.pool.run_all()

    notice = world.notifier.last
    assert (notice.kind, notice.cause) == (
        FailureKind.COMMAND,
        "bots.backtest.backtest",
    )
    assert "unreachable" not in notice.headline
    assert notice.detail == "klines store unreachable"
    assert view.status.text() == "The run failed."
    assert "unreachable" not in view.status.text() and view.run_button.isEnabled()
    world.workbench.shutdown()


def test_a_sync_that_raised_is_told_as_a_sync_failure(qtbot: Any) -> None:
    class _Down(FakeMarketDataSync):
        def sync(self, request) -> None:  # type: ignore[no-untyped-def]
            raise TimeoutError("exchange timed out")

    world = build_workbench(stored=False)
    world.workbench.shutdown()
    world = build_workbench(stored=False)
    down = _Down()
    world.workbench.view  # noqa: B018 - the page is built
    qtbot.addWidget(world.workbench.view)
    world.workbench._presenter._coordinator._sync = down  # the verified fake that fails
    world.workbench.follow(selection())
    _run(world, qtbot)
    world.pool.run_all()
    qtbot.mouseClick(world.workbench.view.sync_button, Qt.MouseButton.LeftButton)

    world.pool.run_all()

    notice = world.notifier.last
    assert (notice.kind, notice.cause) == (FailureKind.COMMAND, "bots.backtest.sync")
    assert "sync" in notice.headline and "timed out" not in notice.headline
    world.workbench.shutdown()


def test_cancel_with_nothing_running_does_nothing(world: WorkbenchWorld) -> None:
    """A shortcut or a menu command can reach Cancel while the button is off."""
    world.workbench.follow(selection())

    world.workbench.view.cancel_requested.emit()

    assert world.workbench.view.status.text() == ""
    assert _buttons(world.workbench.view) == {"Run backtest": True, "Cancel": False}


def test_a_run_without_funding_that_needs_a_sync_runs_again_without_funding(
    qtbot: Any,
) -> None:
    world = build_workbench(stored=False, storing_sync=True)
    view = world.workbench.view
    qtbot.addWidget(view)
    world.workbench.follow(selection())
    view.run_without_funding_requested.emit()
    world.pool.run_all()

    qtbot.mouseClick(view.sync_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert [q.request.funding for q in world.dispatcher.queries] == [
        FundingRequirement.OPTIONAL,
        FundingRequirement.OPTIONAL,
    ]
    world.workbench.shutdown()

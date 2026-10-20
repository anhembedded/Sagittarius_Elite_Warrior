"""`EPIC-040D` — the workbench's sandbox: edits go to a copy, a run carries the copy, the bot is never
touched, and a plan the kind's own rules refuse is not replayed (`EPIC-040C` pinned the session and
the judge; this pins them through the page)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest
from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_selection import (
    WorkbenchSelection,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.backtest.sandbox_fixtures import (
    SAVED,
    bot,
    market,
)

from .workbench_fixtures import WorkbenchWorld, build_workbench, selection

SAME = "The same as the bot's plan."


@pytest.fixture
def world(qtbot: Any) -> Iterator[WorkbenchWorld]:
    built = build_workbench()
    qtbot.addWidget(built.workbench.page)
    yield built
    built.workbench.shutdown()


def _edit(world: WorkbenchWorld, **changes: str) -> None:
    world.workbench.view.config_edited.emit({**SAVED, **changes})


def test_the_page_says_it_is_a_simulation_and_which_bot_it_copies(
    world: WorkbenchWorld,
) -> None:
    world.workbench.follow(selection("a3f9c1"))

    view = world.workbench.view
    assert view.banner.text().startswith("Simulation only.")
    assert "a3f9c1" in view.source.text() and "not the bot's plan" in view.source.text()
    assert view.editor is not None
    assert not view.reset_button.isEnabled()


def test_an_edit_runs_with_the_edit_and_leaves_the_bot_alone(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    chosen = selection()
    world.workbench.follow(chosen)

    _edit(world, upper="71000")
    qtbot.mouseClick(world.workbench.view.run_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    sent = world.dispatcher.queries[-1].request.config
    assert sent["upper"] == "71000" and sent != chosen.bot.config
    assert chosen.bot.config == SAVED
    assert "upper" in world.workbench.view.changed.text()
    assert world.workbench.view.reset_button.isEnabled()


def test_reset_puts_the_bots_plan_back(world: WorkbenchWorld, qtbot: Any) -> None:
    world.workbench.follow(selection())
    _edit(world, upper="71000")

    qtbot.mouseClick(world.workbench.view.reset_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(world.workbench.view.run_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert world.dispatcher.queries[-1].request.config == SAVED
    assert world.workbench.view.changed.text() == SAME
    assert not world.workbench.view.reset_button.isEnabled()


def test_a_plan_the_kind_refuses_is_not_replayed_and_says_why(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    world.workbench.follow(selection())

    _edit(world, upper="1", lower="2")

    view = world.workbench.view
    assert not view.run_button.isEnabled()
    assert view.run_button.toolTip().startswith("The parameters are refused")
    assert view.status.text() == view.run_button.toolTip()
    assert world.dispatcher.queries == []


def test_what_a_simulation_cannot_check_is_said_not_judged(
    world: WorkbenchWorld,
) -> None:
    world.workbench.follow(selection())

    text = world.workbench.view.verdicts.text()
    assert "Not checked in a simulation" in text


def test_another_bot_after_an_edit_asks_before_it_replaces_and_blocks_run(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection("a3f9c1"))
    _edit(world, upper="71000")

    world.workbench.follow(selection("b7e2d4"))

    assert view.question.isVisibleTo(view)
    assert not view.run_button.isEnabled()
    assert view.status.text() == "Answer the question above first."
    assert view.editor is not None and not view.editor.lower_price.isEnabled()  # type: ignore[attr-defined]


def test_replace_my_edits_copies_the_new_bots_plan(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection("a3f9c1"))
    _edit(world, upper="71000")
    world.workbench.follow(selection("b7e2d4"))

    qtbot.mouseClick(view.replace_button, Qt.MouseButton.LeftButton)

    assert "b7e2d4" in view.source.text() and view.changed.text() == SAME
    assert not view.question.isVisibleTo(view) and view.run_button.isEnabled()


def test_keep_my_edits_stays_on_the_old_bot_and_does_not_ask_again(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection("a3f9c1"))
    _edit(world, upper="71000")
    world.workbench.follow(selection("b7e2d4"))

    qtbot.mouseClick(view.keep_button, Qt.MouseButton.LeftButton)
    world.workbench.follow(selection("b7e2d4"))

    assert "a3f9c1" in view.source.text()
    assert not view.question.isVisibleTo(view) and view.run_button.isEnabled()


def test_the_editor_shows_the_bots_saved_plan_and_reset_shows_it_again(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    world.workbench.follow(selection())
    editor = world.workbench.view.editor
    assert editor is not None and editor.config() == SAVED

    _edit(world, upper="71000")
    editor.set_config({**SAVED, "upper": "71000"})
    qtbot.mouseClick(world.workbench.view.reset_button, Qt.MouseButton.LeftButton)

    assert editor.config() == SAVED


def test_a_run_requested_anyway_still_does_not_replay_a_refused_plan(
    world: WorkbenchWorld,
) -> None:
    """The button is off, but the page's own signal is not the only way to a run (a shortcut,
    `EPIC-040E`'s menu command): the presenter refuses it as well."""
    world.workbench.follow(selection())
    _edit(world, upper="1", lower="2")

    world.workbench.view.run_requested.emit()
    world.pool.run_all()

    assert world.dispatcher.queries == []


def test_the_page_says_whose_fees_a_run_charges(world: WorkbenchWorld) -> None:
    world.workbench.follow(selection())

    assert "your account's fees" in world.workbench.view.source.text()
    assert "maker 0.10%, taker 0.10%" in world.workbench.view.source.text()


def _other_symbol_selection(bot_id: str) -> WorkbenchSelection:
    other = replace(bot(bot_id), symbol="ETHUSDT")
    planner = market()
    terms = replace(planner.terms, maker_fee=Decimal("0.002"), min_notional=Decimal(7))
    return WorkbenchSelection(other, replace(planner, terms=terms))


def test_keeping_edits_across_another_bot_keeps_the_sandbox_with_its_own_markets_numbers(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    """The sandbox copies bot A; bot B's symbol has other tick, step, notional and fees. The run is
    A's symbol, so it is judged and replayed by A's numbers, not B's."""
    view = world.workbench.view
    first = selection("a3f9c1")
    world.workbench.follow(first)
    _edit(world, upper="71000")
    world.workbench.follow(_other_symbol_selection("b7e2d4"))
    qtbot.mouseClick(view.keep_button, Qt.MouseButton.LeftButton)
    world.workbench.follow(_other_symbol_selection("b7e2d4"))

    qtbot.mouseClick(view.run_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    sent = world.dispatcher.queries[-1].request
    assert sent.symbol == "BTCUSDT" and sent.terms == first.market.terms
    assert "maker 0.10%" in view.source.text()


def test_a_run_in_flight_when_the_question_opens_finishes_for_the_sandboxs_own_bot(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    first = selection("a3f9c1")
    world.workbench.follow(first)
    _edit(world, upper="71000")
    qtbot.mouseClick(view.run_button, Qt.MouseButton.LeftButton)

    world.workbench.follow(_other_symbol_selection("b7e2d4"))
    world.pool.run_all()

    assert view.question.isVisibleTo(view) and not view.run_button.isEnabled()
    assert view.status.text() == "Backtest done."
    assert view.summary_text()["candles"] == "96"
    assert world.dispatcher.queries[-1].request.terms == first.market.terms


def test_replacing_the_edits_takes_the_new_bots_market_numbers(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection("a3f9c1"))
    _edit(world, upper="71000")
    other = _other_symbol_selection("b7e2d4")
    world.workbench.follow(other)

    qtbot.mouseClick(view.replace_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(view.run_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    sent = world.dispatcher.queries[-1].request
    assert sent.symbol == "ETHUSDT" and sent.terms == other.market.terms
    assert "maker 0.20%" in view.source.text()


def test_the_same_bot_id_on_another_symbol_is_not_the_sandboxs_source(
    world: WorkbenchWorld,
) -> None:
    first = selection("a3f9c1")
    world.workbench.follow(first)
    _edit(world, upper="71000")

    world.workbench.follow(_other_symbol_selection("a3f9c1"))

    assert "maker 0.10%" in world.workbench.view.source.text()

"""`EPIC-039J` — every Futures state of the Bots screen has a frame the owner can look at.

@details A frame is the real screen filled with the real planner's verdicts, so each test reads
what a frame says, not that it built."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.preview_frames import (
    FRAMES,
    build_frame,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)


def _panel(view: BotsView) -> GridPanel:
    panel = view.findChild(GridPanel)
    assert panel is not None
    return panel


def test_every_state_a_futures_bot_adds_has_a_frame() -> None:
    assert set(FRAMES) == {
        "futures_long_plan",
        "futures_short_plan",
        "futures_neutral_plan",
        "futures_refused_plan",
        "futures_liquidation_warning",
        "futures_drift_halt",
    }


@pytest.mark.parametrize("name", sorted(FRAMES))
def test_each_frame_builds_and_draws(qtbot, name: str) -> None:
    view = build_frame(name)
    qtbot.addWidget(view)

    assert isinstance(view, BotsView)
    assert not view.grab().isNull()
    assert view.model.selected is not None
    assert view.model.selected.venue.display_name == "Futures Testnet"


def test_the_neutral_plan_shows_two_liquidation_estimates(qtbot) -> None:
    view = build_frame("futures_neutral_plan")
    qtbot.addWidget(view)

    lines = _panel(view).exposure.liquidation.text().splitlines()

    assert [line.split(":")[0] for line in lines] == ["Long", "Short"]
    assert all("(estimate)" in line for line in lines)


def test_the_long_and_short_plans_show_one_each(qtbot) -> None:
    for name, side in (("futures_long_plan", "Long"), ("futures_short_plan", "Short")):
        view = build_frame(name)
        qtbot.addWidget(view)

        (line,) = _panel(view).exposure.liquidation.text().splitlines()

        assert line.startswith(f"{side}:")


def test_the_refused_plan_says_so_in_words_on_its_leverage_and_its_row(qtbot) -> None:
    view = build_frame("futures_refused_plan")
    qtbot.addWidget(view)
    panel = _panel(view)

    assert "Blocks Start" in panel.field_error_text("leverage")
    assert panel.exposure.liquidation.text().startswith("Blocks Start:")
    assert any("Refused" in line for line in view.model.verdict_lines)


def test_the_liquidation_warning_is_advice_not_a_block(qtbot) -> None:
    view = build_frame("futures_liquidation_warning")
    qtbot.addWidget(view)

    text = _panel(view).exposure.liquidation.text()

    assert text.startswith("Advice:") and "before the exit" in text


def test_the_drift_halt_says_what_changed_and_shows_the_costs_apart(qtbot) -> None:
    view = build_frame("futures_drift_halt")
    qtbot.addWidget(view)
    facts = view.model.facts

    assert facts is not None
    assert "leverage on the exchange is 5x" in facts.state
    assert facts.shows_costs
    assert facts.commissions != facts.grid_profit

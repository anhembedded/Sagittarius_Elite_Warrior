"""`BOT-205` meets `EPIC-040D` — the replay chart reads in the application's display time zone, like the
Live chart it will sit beside (`EPIC-040E`), and offers the same drop-down."""

from __future__ import annotations

from typing import Any

import pytest
from Sagittarius_Elite_Warrior.tests.chart_axis_labels import drawn_labels, utc_range

from .workbench_fixtures import build_workbench, selection


def test_the_replay_chart_follows_the_shared_display_zone(qtbot: Any) -> None:
    world = build_workbench()
    view = world.workbench.view
    qtbot.addWidget(view)
    world.workbench.follow(selection())
    plot = view.card.plot_layout.main_plot
    before = plot.getAxis("bottom").display_zone

    assert world.timezone.set_zone("Asia/Ho_Chi_Minh")

    assert plot.getAxis("bottom").display_zone == "Asia/Ho_Chi_Minh"
    assert before != "Asia/Ho_Chi_Minh"
    world.workbench.shutdown()


@pytest.mark.parametrize(
    ("zone", "window", "expected", "absent"),
    [
        pytest.param(
            "Asia/Ho_Chi_Minh",
            utc_range(10, 2, 6),
            {"10:00", "12:00"},
            {"03:00"},
            id="east",
        ),
        pytest.param(
            "America/New_York",
            utc_range(10, 10, 6),
            {"06:00", "08:00"},
            {"12:00"},
            id="west",
        ),
    ],
)
def test_the_equity_curve_axis_reads_in_the_shared_display_zone(
    qtbot: Any,
    zone: str,
    window: tuple[float, float],
    expected: set[str],
    absent: set[str],
) -> None:
    """`BUG-243`: the equity pane drew a plain date axis, in the machine's clock."""
    world = build_workbench()
    view = world.workbench.view
    qtbot.addWidget(view)

    assert world.timezone.set_zone(zone)
    labels = set(drawn_labels(view.equity.plot, window))

    assert expected <= labels
    assert not absent & labels
    world.workbench.shutdown()


def test_an_equity_curve_built_after_the_choice_reads_in_the_chosen_zone(
    qtbot: Any,
) -> None:
    """The zone is already set when the workbench opens (a zone restored from saved state)."""
    world = build_workbench(zone="Asia/Ho_Chi_Minh")
    view = world.workbench.view
    qtbot.addWidget(view)

    labels = set(drawn_labels(view.equity.plot, utc_range(10, 2, 6)))

    assert {"10:00", "12:00"} <= labels
    world.workbench.shutdown()

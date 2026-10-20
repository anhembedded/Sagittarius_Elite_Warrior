"""`BOT-205` meets `EPIC-040D` — the replay chart reads in the application's display time zone, like the
Live chart it will sit beside (`EPIC-040E`), and offers the same drop-down."""

from __future__ import annotations

from typing import Any

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

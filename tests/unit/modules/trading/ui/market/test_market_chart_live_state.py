"""`EPIC-034G` — a Market chart says whether it is live, and the user starts
and stops it: History until the user opens the mode or asks, Live after, and
the stream released by Stop live."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_fsm_matrix import (
    LiveChartCommand,
    LiveChartState,
)

S = LiveChartState


def test_a_chart_restored_without_the_users_intent_is_history(build, threads):
    presenter = build()

    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()

    chart = presenter.charts["BTCUSDT"]
    assert chart.live_state is S.HISTORY
    assert chart.chart.findChild(object, "liveStateLabel").text() == "History"


def test_the_users_own_open_takes_the_chart_live(build, threads):
    presenter = build()

    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    threads.run_all()

    assert presenter.charts["BTCUSDT"].live_state is S.LIVE


def test_go_live_on_a_restored_chart_connects_it_and_stop_live_returns(build, threads):
    presenter = build()
    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()
    chart = presenter.charts["BTCUSDT"]

    chart.run_command(LiveChartCommand.GO_LIVE)
    assert chart.live_state is S.CONNECTING
    threads.run_all()
    assert chart.live_state is S.LIVE

    chart.run_command(LiveChartCommand.STOP_LIVE)
    threads.run_all()
    assert chart.live_state is S.HISTORY

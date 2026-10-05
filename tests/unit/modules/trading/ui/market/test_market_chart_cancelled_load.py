"""A first window's load that was cancelled says nothing (`BUG-150`).

A Market tab closed while its first window loads: the load's worker runs
after the tab's `MarketChart` is gone, and nothing it says may be emitted on
that object. A load replaced by a new one: its settle, already on its way,
must not end the new one's loading."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)


def test_a_tab_closed_while_its_first_window_loads_reports_nothing(build, threads):
    presenter = build()
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    threads.run_all()
    entries = len(presenter.view.log.entries)

    presenter.view.symbol_opened.emit("ETHUSDT")
    presenter.view.chart_closed.emit("ETHUSDT")
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    threads.run_all()
    QCoreApplication.processEvents()

    assert "ETHUSDT" not in presenter.charts
    assert not [
        e.message
        for e in presenter.view.log.entries[entries:]
        if "ETHUSDT" in e.message
    ]


def test_a_replaced_loads_settle_does_not_end_the_new_ones_loading(build, threads):
    presenter = build()
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    threads.run_all()
    chart = presenter.charts["BTCUSDT"]
    replaced = chart._token

    chart.chart.toolbar.sig_timeframe_changed.emit("1h")
    chart._load_settled.emit(replaced)

    assert chart.loading
    threads.run_all()
    assert not chart.loading

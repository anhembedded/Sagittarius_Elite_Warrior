"""`BUG-213` — a report already queued when a chart shuts down draws nothing.

A worker reports to the chart through a Qt signal. The coordinator checks the
token first (`BUG-150`), so a report is emitted only while its request is live;
but the emit queues the call to the Qt thread, and between the queueing and the
delivery the Qt thread can shut the chart down and delete its `ChartCard`. The
`LiveCandleChart` is a `QObject` the owner holds (the Market presenter, not the
card), so it outlives the card and its slot still runs, on widgets C++ has
already freed.

Each test queues the report from a real thread, shuts the chart down, really
deletes the card, then lets the event loop deliver; no sleep, no mock of the
slot.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QObject, SignalInstance
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_candle_chart import (
    LiveCandleChart,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_fsm_matrix import (
    LiveChartState,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from Sagittarius_Elite_Warrior.tests.unit.support.charting.live_chart.live_chart_fixtures import (
    OWNER,
    Clock,
    HeldThreadManager,
    ScriptedCandleFeed,
)

_SYMBOL = "BTCUSDT"


def _emit_from_a_worker(signal: SignalInstance, *args: object) -> None:
    """Emits as a pool worker does: from another thread, so the call to the
    chart is queued to the Qt thread instead of running at once."""
    worker = threading.Thread(target=lambda: signal.emit(*args))
    worker.start()
    worker.join()


def _delete_now(card: ChartCard) -> None:
    """What a closed tab's `deleteLater()` comes to once the loop runs."""
    card.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(card), "the card must really be freed"


def _chart_held_by_an_owner(owner: QObject) -> tuple[LiveCandleChart, ChartCard]:
    """The Market's shape: the card is a widget of the window, the chart a
    child of the presenter, which outlives the window. Its loads are held, so
    it stays Connecting after Go live, as it is while the exchange answers."""
    card = ChartCard(_SYMBOL)
    ports = LiveChartPorts(
        thread_manager=HeldThreadManager(),
        feed=ScriptedCandleFeed(),
        stream_owner=OWNER,
        interval="1m",
        market=MarketType.SPOT,
        clock=Clock(),
        notifier=RecordingNotifier(),
        scope="test",
    )
    return LiveCandleChart(card, ports, owner), card


#: Each report a worker sends a chart, as a function of the chart: the signal
#: and the arguments the coordinator's callbacks give it.
_REPORTS: dict[str, Callable[[LiveCandleChart], tuple[SignalInstance, tuple]]] = {
    "stream opened": lambda chart: (
        chart._stream_opened,
        (chart._token, "Live for BTCUSDT."),
    ),
    "stream lost": lambda chart: (
        chart._stream_lost,
        (chart._token, "The stream stopped.", "detail"),
    ),
    "history": lambda chart: (chart._history, (_SYMBOL, [], [], [])),
}


@pytest.mark.parametrize("report", list(_REPORTS))
def test_a_report_queued_before_shutdown_draws_nothing_on_the_deleted_card(
    qapp, qtbot, report: str
) -> None:
    owner = QObject()
    chart, card = _chart_held_by_an_owner(owner)
    chart.show_symbol(_SYMBOL)
    chart.go_live()
    assert chart.live_state is LiveChartState.CONNECTING
    signal, args = _REPORTS[report](chart)
    _emit_from_a_worker(signal, *args)

    chart.shutdown()
    _delete_now(card)
    with qtbot.capture_exceptions() as caught:
        qapp.processEvents()

    assert [str(error) for _kind, error, _tb in caught] == []

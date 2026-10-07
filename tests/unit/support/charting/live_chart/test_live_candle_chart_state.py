"""`EPIC-034G` — a chart says whether it is live, and the user starts and
stops it. The state is the coordinator's own lifecycle seen from the chart:
each test drives a real `LiveCandleChart` over a scripted feed and reads the
chip a user sees."""

from __future__ import annotations

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_candle_chart import (
    LiveCandleChart,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_fsm_matrix import (
    LiveChartCommand,
    LiveChartState,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_state_chip import (
    age_text,
)
from Sagittarius_Elite_Warrior.tests.unit.support.charting.live_chart.live_chart_fixtures import (
    Clock,
    HeldThreadManager,
    InlineThreadManager,
    ScriptedCandleFeed,
    build_chart,
)

S = LiveChartState
C = LiveChartCommand


def _command_text(card) -> str:
    return card.findChild(object, "act_liveCommand").text()


def test_a_chart_opens_on_history_and_offers_go_live(qapp) -> None:
    feed = ScriptedCandleFeed()
    chart, card = build_chart(feed)

    chart.show_symbol("BTCUSDT")

    assert chart.live_state is S.HISTORY
    assert card.findChild(object, "liveStateLabel").text() == "History"
    assert _command_text(card) == "Go live"
    assert "sync" not in feed.calls and "start_stream" not in feed.calls


def test_go_live_syncs_streams_and_reads_live(qapp) -> None:
    feed = ScriptedCandleFeed()
    chart, card = build_chart(feed)
    chart.show_symbol("BTCUSDT")

    chart.run_command(C.GO_LIVE)

    assert chart.live_state is S.LIVE
    assert feed.calls.count("start_stream") == 1
    assert _command_text(card) == "Stop live"
    assert card.findChild(object, "liveStateLabel").text().startswith("Live")


def test_a_failed_stream_is_an_error_with_its_reason_and_a_retry(qapp) -> None:
    feed = ScriptedCandleFeed()
    feed.stream_message = "no route to the exchange"
    chart, card = build_chart(feed)
    chart.show_symbol("BTCUSDT")

    chart.run_command(C.GO_LIVE)

    assert chart.live_state is S.ERROR
    assert "no route to the exchange" in chart.live_error
    label = card.findChild(object, "liveStateLabel")
    assert label.text().startswith("Error: Could not open live stream")
    assert "no route to the exchange" in label.toolTip()
    assert _command_text(card) == "Retry"


def test_retry_asks_the_coordinator_again_and_can_succeed(qapp) -> None:
    feed = ScriptedCandleFeed()
    feed.stream_message = "refused"
    chart, _card = build_chart(feed)
    chart.show_symbol("BTCUSDT")
    chart.run_command(C.GO_LIVE)
    assert chart.live_state is S.ERROR

    feed.stream_message = None
    chart.run_command(C.RETRY)

    assert chart.live_state is S.LIVE
    assert chart.live_error == ""
    assert feed.calls.count("start_stream") == 2


def test_a_failed_sync_is_an_error_too(qapp) -> None:
    feed = ScriptedCandleFeed()
    feed.sync_error = "interval refused"
    chart, _card = build_chart(feed)
    chart.show_symbol("BTCUSDT")

    chart.run_command(C.GO_LIVE)

    assert chart.live_state is S.ERROR
    assert "interval refused" in chart.live_error
    assert "start_stream" not in feed.calls


def test_stop_live_releases_the_stream_and_returns_to_history(qapp) -> None:
    feed = ScriptedCandleFeed()
    chart, card = build_chart(feed)
    chart.show_symbol("BTCUSDT")
    chart.run_command(C.GO_LIVE)

    chart.run_command(C.STOP_LIVE)

    assert chart.live_state is S.HISTORY
    assert not chart.is_live
    assert "stop_stream" in feed.calls
    assert _command_text(card) == "Go live"


def test_cancel_while_connecting_returns_to_history_and_opens_no_stream(qapp) -> None:
    feed = ScriptedCandleFeed()
    threads = HeldThreadManager()
    chart, card = build_chart(feed, threads=threads)
    chart.show_symbol("BTCUSDT")
    threads.run_all()
    chart.run_command(C.GO_LIVE)
    assert chart.live_state is S.CONNECTING
    assert _command_text(card) == "Cancel"

    chart.run_command(C.CANCEL)
    threads.run_all()

    assert chart.live_state is S.HISTORY
    assert not chart.is_live
    assert "start_stream" not in feed.calls


def test_a_report_that_was_on_its_way_when_the_user_cancelled_moves_nothing(
    qapp,
) -> None:
    """The coordinator's report is queued to the Qt thread; a cancel can land
    first, and the table drops what it declares no move for."""
    feed = ScriptedCandleFeed()
    chart, _card = build_chart(feed)
    chart.show_symbol("BTCUSDT")
    chart.run_command(C.GO_LIVE)
    chart.run_command(C.STOP_LIVE)

    chart._stream_opened.emit(chart._token, "Streaming live data for BTCUSDT.")
    chart._stream_lost.emit(chart._token, "a late failure")

    assert chart.live_state is S.HISTORY
    assert chart.live_error == ""


def test_a_command_the_state_does_not_offer_changes_nothing(qapp) -> None:
    feed = ScriptedCandleFeed()
    chart, _card = build_chart(feed)
    chart.show_symbol("BTCUSDT")
    feed.calls.clear()

    chart.run_command(C.STOP_LIVE)
    chart.run_command(C.RETRY)

    assert chart.live_state is S.HISTORY
    assert feed.calls == []


def test_a_second_go_live_asks_for_one_stream(qapp) -> None:
    feed = ScriptedCandleFeed()
    chart, _card = build_chart(feed)
    chart.show_symbol("BTCUSDT")

    chart.go_live()
    chart.go_live()

    assert feed.calls.count("start_stream") == 1


def test_a_new_symbol_while_live_connects_again(qapp) -> None:
    feed = ScriptedCandleFeed()
    chart, _card = build_chart(feed)
    chart.show_symbol("BTCUSDT")
    chart.run_command(C.GO_LIVE)
    seen: list[LiveChartState] = []
    chart.liveStateChanged.connect(seen.append)

    chart.show_symbol("ETHUSDT")

    assert seen == [S.CONNECTING, S.LIVE]


def test_live_reports_the_age_of_the_last_update(qapp) -> None:
    feed = ScriptedCandleFeed()
    clock = Clock()
    chart, card = build_chart(feed, clock)
    chart.show_symbol("BTCUSDT")
    chart.run_command(C.GO_LIVE)
    chip = card.findChild(object, "liveStateChip")
    assert chart.last_update_age() is None
    assert "waiting for the first update" in chip.text

    chart.apply_candle(candle("BTCUSDT", 0))
    clock.now += 7

    assert chart.last_update_age() == 7
    chip.show_state(S.LIVE, "")
    assert chip.text == "Live · updated 7 s ago"


def test_the_age_is_written_in_plain_units() -> None:
    assert age_text(None) == "waiting for the first update"
    assert age_text(0.4) == "updated 0 s ago"
    assert age_text(59.9) == "updated 59 s ago"
    assert age_text(120) == "updated 2 min ago"
    assert age_text(7200) == "updated 2 h ago"


def test_the_commands_are_in_the_chart_context_menu(qapp) -> None:
    chart, card = build_chart(ScriptedCandleFeed())
    action = card.findChild(object, "act_liveCommand")
    assert action in card.plot_layout.main_plot.vb.menu.actions()
    assert chart.live_state is S.HISTORY


def test_closing_the_chart_releases_it_to_history(qapp) -> None:
    feed = ScriptedCandleFeed()
    chart, _card = build_chart(feed)
    chart.show_symbol("BTCUSDT")
    chart.run_command(C.GO_LIVE)

    chart._go_quiet()

    assert chart.live_state is S.HISTORY
    assert "stop_stream" in feed.calls


def test_a_chart_that_only_draws_a_finished_run_offers_no_live_command(qapp) -> None:
    card = ChartCard("BTCUSDT")
    ports = LiveChartPorts(
        thread_manager=InlineThreadManager(),
        feed=ScriptedCandleFeed(),
        stream_owner="test.replay",
        interval="1m",
        market=MarketType.SPOT,
        live_commands=False,
    )
    chart = LiveCandleChart(card, ports, parent=card)

    assert card.findChild(object, "liveStateLabel") is None
    assert chart.live_state is S.HISTORY


def test_a_new_symbol_starts_the_age_again(qapp) -> None:
    chart, _card = build_chart(ScriptedCandleFeed(), Clock())
    chart.show_symbol("BTCUSDT")
    chart.run_command(C.GO_LIVE)
    chart.apply_candle(candle("BTCUSDT", 0))
    assert chart.last_update_age() == 0

    chart.show_symbol("ETHUSDT")

    assert chart.last_update_age() is None


def test_a_report_of_a_replaced_request_moves_nothing(qapp) -> None:
    """The reviewer's case: a report emitted before a new symbol or a Retry
    but delivered after it must neither read Live early nor strand the chip
    on Error."""
    feed = ScriptedCandleFeed()
    threads = HeldThreadManager()
    chart, _card = build_chart(feed, threads=threads)
    chart.show_symbol("BTCUSDT")
    threads.run_all()
    chart.run_command(C.GO_LIVE)
    old = chart._token
    chart.show_symbol("ETHUSDT")  # replaces the request while Connecting
    assert chart.live_state is S.CONNECTING

    chart._stream_opened.emit(old, "old stream")
    chart._stream_lost.emit(old, "old failure")

    assert chart.live_state is S.CONNECTING
    assert chart.live_error == ""
    threads.run_all()
    assert chart.live_state is S.LIVE


def test_the_age_timer_runs_only_while_live_and_rewrites_the_chip(qapp) -> None:
    clock = Clock()
    chart, card = build_chart(ScriptedCandleFeed(), clock)
    chart.show_symbol("BTCUSDT")
    chip = card.findChild(object, "liveStateChip")
    assert not chip._timer.isActive()

    chart.run_command(C.GO_LIVE)
    assert chip._timer.isActive()
    chart.apply_candle(candle("BTCUSDT", 0))
    clock.now += 5
    chip._timer.timeout.emit()
    assert chip.text == "Live · updated 5 s ago"

    chart.run_command(C.STOP_LIVE)
    assert not chip._timer.isActive()


def test_the_menu_action_is_checked_while_connecting_or_live_and_drives_the_chart(
    qapp,
) -> None:
    feed = ScriptedCandleFeed()
    threads = HeldThreadManager()
    chart, _card = build_chart(feed, threads=threads)
    chart.show_symbol("BTCUSDT")
    threads.run_all()
    action = chart.live_stream_action
    assert not action.isChecked()

    action.setChecked(True)  # what the shell's Live stream command does
    assert chart.live_state is S.CONNECTING and action.isChecked()
    threads.run_all()
    assert chart.live_state is S.LIVE

    action.setChecked(False)
    assert chart.live_state is S.HISTORY and not action.isChecked()


def test_checking_the_menu_action_in_error_retries_and_stays_unchecked_if_it_fails(
    qapp,
) -> None:
    feed = ScriptedCandleFeed()
    feed.stream_message = "refused"
    chart, _card = build_chart(feed)
    chart.show_symbol("BTCUSDT")
    chart.run_command(C.GO_LIVE)
    action = chart.live_stream_action
    assert chart.live_state is S.ERROR and not action.isChecked()

    action.setChecked(True)  # Retry; the feed still refuses

    assert feed.calls.count("start_stream") == 2
    assert chart.live_state is S.ERROR and not action.isChecked()


def test_an_error_reason_that_looks_like_markup_is_shown_as_text(qapp) -> None:
    """`BUG-168`: the reason is an exchange's answer."""
    feed = ScriptedCandleFeed()
    feed.stream_message = "<h1>502 Bad Gateway</h1>"
    chart, card = build_chart(feed)
    chart.show_symbol("BTCUSDT")

    chart.run_command(C.GO_LIVE)

    label = card.findChild(object, "liveStateLabel")
    assert label.textFormat() == Qt.TextFormat.PlainText
    assert "<h1>502 Bad Gateway</h1>" in label.toolTip()

"""Tests for BOT-098F6A's Backtest chart host port/adapter/factory.

Covers the seam itself: PythonBacktestChartHost delegates every port
operation to the wrapped ChartCard without reimplementing behavior, the
factory produces a distinct host per call (never shared/cached), and
BackTestView.render_symbol_cards() deterministically tears down the previous
host's ChartCard before building the next one.

A native C++/QML host used to sit behind this same port (BOT-098F6D's
backend-selection/fallback logic, BOT-098F6F's mode-support tests) — deleted
outright (never rendered a production frame); `PythonBacktestChartHost` is
now the sole implementation.
"""

from unittest.mock import patch

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_chart_host import (
    BacktestChartHostFactory,
    PythonBacktestChartHost,
)


def test_host_widget_and_symbol_expose_the_wrapped_chart_card(qapp, request):
    card = ChartCard("ETHUSDT")
    request.addfinalizer(card.deleteLater)
    host = PythonBacktestChartHost(card)

    assert host.widget is card
    assert host.chart_card is card
    assert host.symbol == "ETHUSDT"


def test_host_delegates_every_port_operation_to_the_chart_card(qapp, request):
    card = ChartCard("BTCUSDT")
    request.addfinalizer(card.deleteLater)
    host = PythonBacktestChartHost(card)

    calls = [
        ("add_to_header", (object(),), {}),
        ("set_dev_mode", (True,), {}),
        ("set_display_timezone", ("Asia/Ho_Chi_Minh",), {}),
        ("render_historical_data", ([],), {}),
        ("render_historical_volume", ([],), {}),
        ("set_chart_type", ("candlestick",), {}),
        ("set_volume_visible", (False,), {}),
        # BOT-111: width defaults to 2 and is always forwarded explicitly,
        # even when the caller didn't pass one — matches the pre-existing
        # fixed width IndicatorManager.add_overlay() used before this
        # parameter existed.
        ("add_overlay_indicator", ("ema", "#fff", 2), {}),
        ("add_subplot_indicator", ("rsi", "#fff", 2), {}),
        ("update_indicator_data", ("ema", [1.0], [2.0]), {}),
        ("set_indicator_visible", ("ema", False), {}),
        ("remove_indicator", ("ema",), {}),
        ("set_script_regions", ("k", []), {}),
        ("clear_script_regions", ("k",), {}),
        ("set_script_info", ("k", []), {}),
        ("clear_script_info", ("k",), {}),
        ("set_script_markers", ("k", []), {}),
        ("clear_script_markers", ("k",), {}),
        ("cleanup", (), {}),
    ]
    for method_name, args, kwargs in calls:
        with patch.object(card, method_name) as mocked:
            getattr(host, method_name)(*args, **kwargs)
            mocked.assert_called_once_with(*args, **kwargs)


def test_host_timeframe_operations_go_through_the_toolbar(qapp, request):
    card = ChartCard("BTCUSDT")
    request.addfinalizer(card.deleteLater)
    host = PythonBacktestChartHost(card)

    received: list[str] = []
    host.connect_timeframe_changed(received.append)
    card.toolbar.sig_timeframe_changed.emit("5m")
    assert received == ["5m"]

    host.set_active_timeframe("15m")
    assert card.toolbar._buttons["15m"].isChecked() is True


def test_factory_creates_a_distinct_host_per_call(qapp, request):
    factory = BacktestChartHostFactory()

    first = factory.create("BTCUSDT", use_opengl=False, cached_interaction=False)
    second = factory.create("BTCUSDT", use_opengl=False, cached_interaction=False)
    request.addfinalizer(first.widget.deleteLater)
    request.addfinalizer(second.widget.deleteLater)

    assert isinstance(first, PythonBacktestChartHost)
    assert first is not second
    assert first.chart_card is not second.chart_card
    assert first.widget is not second.widget


def test_factory_passes_render_backend_options_through_to_chart_card(qapp, request):
    factory = BacktestChartHostFactory()

    host = factory.create("BTCUSDT", use_opengl=True, cached_interaction=True)
    request.addfinalizer(host.widget.deleteLater)

    assert host.chart_card._use_opengl is True
    assert host.chart_card.cached_interaction is not None


def test_render_symbol_cards_replacement_cleans_up_the_previous_host(qapp, request):
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    first_cards = view.render_symbol_cards(["BTCUSDT"])
    first_chart_card = first_cards[0].chart_card

    with patch.object(first_chart_card, "cleanup") as mocked_cleanup:
        second_cards = view.render_symbol_cards(["ETHUSDT"])
        mocked_cleanup.assert_called_once()

    assert second_cards[0] is not first_cards[0]
    assert second_cards[0].chart_card is not first_chart_card
    assert second_cards[0].symbol == "ETHUSDT"

"""Tests for BOT-098F6A's Backtest chart host port/adapter/factory, and
BOT-098F6D's backend-selection/fallback logic layered on top of it.

Covers the seam itself: PythonBacktestChartHost delegates every port
operation to the wrapped ChartCard without reimplementing behavior, the
factory produces a distinct host per call (never shared/cached), and
BackTestView.render_symbol_cards() deterministically tears down the previous
host's ChartCard before building the next one.
"""

from unittest.mock import Mock, patch

import pytest

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_runtime import (
    NativeChartRuntimeError,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_chart_host import (
    BacktestChartHostFactory,
    PythonBacktestChartHost,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_host_adapter import (
    NativeBacktestChartHostAdapter,
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
        ("add_overlay_indicator", ("ema", "#fff"), {}),
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

    first = factory.create(
        "BTCUSDT", use_opengl=False, cached_interaction=False, backend="python"
    )
    second = factory.create(
        "BTCUSDT", use_opengl=False, cached_interaction=False, backend="python"
    )
    request.addfinalizer(first.widget.deleteLater)
    request.addfinalizer(second.widget.deleteLater)

    assert isinstance(first, PythonBacktestChartHost)
    assert first is not second
    assert first.chart_card is not second.chart_card
    assert first.widget is not second.widget


def test_factory_passes_render_backend_options_through_to_chart_card(qapp, request):
    factory = BacktestChartHostFactory()

    host = factory.create(
        "BTCUSDT", use_opengl=True, cached_interaction=True, backend="python"
    )
    request.addfinalizer(host.widget.deleteLater)

    assert host.chart_card._use_opengl is True
    assert host.chart_card.cached_interaction is not None


def test_render_symbol_cards_replacement_cleans_up_the_previous_host(qapp, request):
    view = BackTestView()
    view.set_chart_backend("python")
    request.addfinalizer(view.deleteLater)

    first_cards = view.render_symbol_cards(["BTCUSDT"])
    first_chart_card = first_cards[0].chart_card

    with patch.object(first_chart_card, "cleanup") as mocked_cleanup:
        second_cards = view.render_symbol_cards(["ETHUSDT"])
        mocked_cleanup.assert_called_once()

    assert second_cards[0] is not first_cards[0]
    assert second_cards[0].chart_card is not first_chart_card
    assert second_cards[0].symbol == "ETHUSDT"


# --------------------------------------------------------------------------
# BOT-098F6D / BOT-098F6E: backend selection and fallback
# --------------------------------------------------------------------------

_NATIVE_HOST_TARGET = "Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter.NativeBacktestChartHost"


def test_default_backend_is_auto_and_attempts_native(qapp, request):
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
        NativeBacktestChartHost,
    )

    factory = BacktestChartHostFactory()
    fake_native_host = Mock(spec=NativeBacktestChartHost)
    fake_native_host.widget = ChartCard("placeholder")

    with patch(f"{_NATIVE_HOST_TARGET}.create", return_value=fake_native_host):
        host = factory.create("BTCUSDT")
    request.addfinalizer(host.widget.deleteLater)

    assert isinstance(host, NativeBacktestChartHostAdapter)
    assert host.native_host is fake_native_host


def test_default_backend_falls_back_to_python_when_native_unavailable(qapp, request):
    factory = BacktestChartHostFactory()
    with patch(
        f"{_NATIVE_HOST_TARGET}.create",
        side_effect=NativeChartRuntimeError("plugin missing"),
    ):
        host = factory.create("BTCUSDT")
    request.addfinalizer(host.widget.deleteLater)

    assert isinstance(host, PythonBacktestChartHost)


def test_python_backend_never_touches_the_native_module(qapp, request):
    factory = BacktestChartHostFactory()
    with patch(f"{_NATIVE_HOST_TARGET}.create") as mocked_create:
        host = factory.create("BTCUSDT", backend="python")
    request.addfinalizer(host.widget.deleteLater)
    mocked_create.assert_not_called()
    assert isinstance(host, PythonBacktestChartHost)


@pytest.mark.parametrize("backend", ["native", "auto"])
def test_native_backend_returns_the_adapter_on_success(qapp, request, backend):
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
        NativeBacktestChartHost,
    )

    factory = BacktestChartHostFactory()
    fake_native_host = Mock(spec=NativeBacktestChartHost)
    fake_native_host.widget = ChartCard("placeholder")

    with patch(f"{_NATIVE_HOST_TARGET}.create", return_value=fake_native_host):
        host = factory.create("BTCUSDT", backend=backend)
    # host.widget (NativeChartCard) now owns the placeholder ChartCard as a
    # Qt child — deleting it alone is enough; Qt's parent-child cascade
    # handles the child, so deleting both separately double-frees it.
    request.addfinalizer(host.widget.deleteLater)

    assert isinstance(host, NativeBacktestChartHostAdapter)
    assert host.native_host is fake_native_host


@pytest.mark.parametrize("backend", ["native", "auto"])
def test_native_backend_falls_back_to_python_on_construction_failure(
    qapp, request, backend
):
    factory = BacktestChartHostFactory()
    with patch(
        f"{_NATIVE_HOST_TARGET}.create",
        side_effect=NativeChartRuntimeError("plugin missing"),
    ):
        host = factory.create("BTCUSDT", backend=backend)
    request.addfinalizer(host.widget.deleteLater)

    assert isinstance(host, PythonBacktestChartHost)


def test_env_override_python_takes_priority_over_native_argument(
    qapp, request, monkeypatch
):
    monkeypatch.setenv("SAGITTARIUS_BACKTEST_CHART_BACKEND", "python")
    factory = BacktestChartHostFactory()
    with patch(f"{_NATIVE_HOST_TARGET}.create") as mocked_create:
        host = factory.create("BTCUSDT", backend="native")
    request.addfinalizer(host.widget.deleteLater)

    mocked_create.assert_not_called()
    assert isinstance(host, PythonBacktestChartHost)


def test_env_override_native_takes_priority_over_python_argument(
    qapp, request, monkeypatch
):
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
        NativeBacktestChartHost,
    )

    monkeypatch.setenv("SAGITTARIUS_BACKTEST_CHART_BACKEND", "native")
    factory = BacktestChartHostFactory()
    fake_native_host = Mock(spec=NativeBacktestChartHost)
    fake_native_host.widget = ChartCard("placeholder")

    with patch(f"{_NATIVE_HOST_TARGET}.create", return_value=fake_native_host):
        host = factory.create("BTCUSDT", backend="python")
    request.addfinalizer(host.widget.deleteLater)

    assert isinstance(host, NativeBacktestChartHostAdapter)
    assert host.native_host is fake_native_host


# --------------------------------------------------------------------------
# BOT-098F6F: BackTestView supports Native across OHLC, EQUITY, and BOTH modes.
# --------------------------------------------------------------------------


def test_equity_mode_uses_native_when_native_is_configured(qapp, request):
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_canvas_view import (
        ChartDisplayMode,
    )

    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    view.set_chart_backend("native")

    with patch(f"{_NATIVE_HOST_TARGET}.create", side_effect=_fake_native_host_factory):
        view.set_chart_mode(ChartDisplayMode.EQUITY)
        cards = view.render_symbol_cards(["BTCUSDT"])

    assert isinstance(cards[0], NativeBacktestChartHostAdapter)


def test_both_mode_uses_native_when_native_is_configured(qapp, request):
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_canvas_view import (
        ChartDisplayMode,
    )

    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    view.set_chart_backend("native")

    with patch(f"{_NATIVE_HOST_TARGET}.create", side_effect=_fake_native_host_factory):
        view.set_chart_mode(ChartDisplayMode.BOTH)
        cards = view.render_symbol_cards(["BTCUSDT"])

    assert isinstance(cards[0], NativeBacktestChartHostAdapter)


def _fake_native_host_factory():
    """A minimal object satisfying just enough of NativeBacktestChartHost's
    surface for BacktestChartHostFactory._try_create_native() to wrap it."""
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
        NativeBacktestChartHost,
    )

    fake = Mock(spec=NativeBacktestChartHost)
    fake.widget = ChartCard("placeholder")
    return fake


def test_mode_changes_within_native_backend_retain_host_without_rebuild(qapp, request):
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_canvas_view import (
        ChartDisplayMode,
    )

    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    view.set_chart_backend("native")

    with patch(f"{_NATIVE_HOST_TARGET}.create", side_effect=_fake_native_host_factory):
        view.render_symbol_cards(["BTCUSDT"])
        first_host = view.chart_cards[0]
        assert isinstance(first_host, NativeBacktestChartHostAdapter)

        rebuilt = view.set_chart_mode(ChartDisplayMode.EQUITY)
        assert rebuilt is False
        assert view.chart_cards[0] is first_host
        assert isinstance(view.chart_cards[0], NativeBacktestChartHostAdapter)

        rebuilt = view.set_chart_mode(ChartDisplayMode.BOTH)
        assert rebuilt is False
        assert view.chart_cards[0] is first_host
        assert isinstance(view.chart_cards[0], NativeBacktestChartHostAdapter)

        rebuilt = view.set_chart_mode(ChartDisplayMode.OHLC)
        assert rebuilt is False
        assert view.chart_cards[0] is first_host
        assert isinstance(view.chart_cards[0], NativeBacktestChartHostAdapter)

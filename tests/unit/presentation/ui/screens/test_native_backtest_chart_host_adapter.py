"""Unit tests for BOT-098F6D's NativeBacktestChartHostAdapter — the bridge
between IBacktestChartHost (BOT-098F6A) and NativeBacktestChartHost
(BOT-098F6B/F6C). NativeBacktestChartHost itself is mocked throughout, so
these tests do not need the native plugin built.
"""

from unittest.mock import Mock

import pytest

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
    NativeBacktestChartHost,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_host_adapter import (
    NativeBacktestChartHostAdapter,
    NativeUnsupportedFeatureError,
)

_CANDLES = [(1_700_000_000.0, 10.0, 12.0, 9.0, 11.0)]
_VOLUMES = [(1_700_000_000.0, 100.0, True)]


@pytest.fixture
def fake_native_host(qapp, request):
    host = Mock(spec=NativeBacktestChartHost)
    host.widget = ChartCard("placeholder")
    host.submit_ohlcv.return_value = True
    host.submit_indicators.return_value = True
    host.submit_markers.return_value = True
    return host


@pytest.fixture
def adapter(qapp, request, fake_native_host):
    result = NativeBacktestChartHostAdapter("BTCUSDT", fake_native_host)
    request.addfinalizer(result.widget.deleteLater)
    return result


def test_symbol_and_widget(adapter, fake_native_host):
    assert adapter.symbol == "BTCUSDT"
    assert adapter.native_host is fake_native_host
    # The native widget is embedded inside the card the port exposes.
    assert adapter.widget.isAncestorOf(fake_native_host.widget)


def test_set_dev_mode_and_timezone_delegate_directly(adapter, fake_native_host):
    adapter.set_dev_mode(True)
    fake_native_host.set_dev_fps_enabled.assert_called_once_with(True)

    adapter.set_display_timezone("Asia/Ho_Chi_Minh")
    fake_native_host.set_display_timezone.assert_called_once_with("Asia/Ho_Chi_Minh")


def test_render_historical_data_and_volume_combine_into_one_submit_ohlcv(
    adapter, fake_native_host
):
    adapter.render_historical_data(_CANDLES)
    fake_native_host.submit_ohlcv.assert_not_called()

    adapter.render_historical_volume(_VOLUMES)
    fake_native_host.submit_ohlcv.assert_called_once()
    args, kwargs = fake_native_host.submit_ohlcv.call_args
    assert args[0] == _CANDLES
    assert args[1] == _VOLUMES
    assert kwargs["action_id"] == 1
    assert kwargs["generation"] == 1


def test_render_historical_volume_without_a_preceding_candles_call_is_rejected(
    adapter,
):
    with pytest.raises(NativeUnsupportedFeatureError, match="without a preceding"):
        adapter.render_historical_volume(_VOLUMES)


def test_a_rejected_ohlcv_submission_raises(adapter, fake_native_host):
    fake_native_host.submit_ohlcv.return_value = False
    adapter.render_historical_data(_CANDLES)
    with pytest.raises(NativeUnsupportedFeatureError, match="rejected"):
        adapter.render_historical_volume(_VOLUMES)


@pytest.mark.parametrize("chart_type", ["candlestick", "line"])
def test_supported_chart_types_are_accepted_silently(adapter, chart_type):
    adapter.set_chart_type(chart_type)  # must not raise


@pytest.mark.parametrize("chart_type", ["heikin-ashi", "area", "renko"])
def test_unsupported_chart_type_is_rejected(adapter, chart_type):
    with pytest.raises(NativeUnsupportedFeatureError, match="candlestick/line only"):
        adapter.set_chart_type(chart_type)


def test_line_chart_submits_pending_candles_without_volume(adapter, fake_native_host):
    adapter.render_historical_data(_CANDLES)
    adapter.set_chart_type("line")
    fake_native_host.submit_ohlcv.assert_called_once()
    args, _kwargs = fake_native_host.submit_ohlcv.call_args
    assert args[0] == _CANDLES
    assert args[1] == []


def test_indicator_lines_resubmit_the_full_active_set_on_every_change(
    adapter, fake_native_host
):
    adapter.add_overlay_indicator("ema_fast", "#ff0000")
    adapter.update_indicator_data("ema_fast", [1.0], [10.0])
    assert fake_native_host.submit_indicators.call_count == 1
    (first_series,), _ = fake_native_host.submit_indicators.call_args
    assert len(first_series) == 1

    adapter.add_overlay_indicator("ema_slow", "#00ff00")
    adapter.update_indicator_data("ema_slow", [1.0], [20.0])
    (second_series,), _ = fake_native_host.submit_indicators.call_args
    assert len(second_series) == 2  # both ema_fast and ema_slow resubmitted

    adapter.remove_indicator("ema_fast")
    (third_series,), _ = fake_native_host.submit_indicators.call_args
    assert len(third_series) == 1


def test_update_indicator_data_without_registration_is_rejected(adapter):
    with pytest.raises(NativeUnsupportedFeatureError, match="without a preceding"):
        adapter.update_indicator_data("ghost", [1.0], [1.0])


def test_add_subplot_indicator_registers_and_submits(adapter, fake_native_host):
    adapter.add_subplot_indicator("equity", "#3b82f6")
    adapter.update_indicator_data("equity", [1.0], [100.0])
    assert fake_native_host.submit_indicators.call_count == 1
    (series,), _ = fake_native_host.submit_indicators.call_args
    assert len(series) == 1


def test_set_indicator_visible_toggles_submission(adapter, fake_native_host):
    adapter.add_overlay_indicator("ema", "#ff0000")
    adapter.update_indicator_data("ema", [1.0], [10.0])
    assert fake_native_host.submit_indicators.call_count == 1

    adapter.set_indicator_visible("ema", False)
    assert fake_native_host.submit_indicators.call_count == 2
    (series,), _ = fake_native_host.submit_indicators.call_args
    assert len(series) == 0  # hidden

    adapter.set_indicator_visible("ema", True)
    assert fake_native_host.submit_indicators.call_count == 3
    (series,), _ = fake_native_host.submit_indicators.call_args
    assert len(series) == 1  # visible again


def test_trade_flag_markers_are_submitted(adapter, fake_native_host):
    markers = [(1_700_000_000.0, 10.5, "MUA (LONG)", "#26a69a", "up")]
    adapter.set_script_markers("backtest_trades", markers)
    fake_native_host.submit_markers.assert_called_once()
    (submitted,), _kwargs = fake_native_host.submit_markers.call_args
    assert submitted == markers


def test_non_trade_marker_keys_are_rejected(adapter, fake_native_host):
    with pytest.raises(NativeUnsupportedFeatureError, match="trade-flags key"):
        adapter.set_script_markers("some_reference_script", [])
    fake_native_host.submit_markers.assert_not_called()


def test_script_regions_and_info_are_rejected(adapter):
    with pytest.raises(NativeUnsupportedFeatureError, match="regions"):
        adapter.set_script_regions("k", [])
    with pytest.raises(NativeUnsupportedFeatureError, match="info"):
        adapter.set_script_info("k", [])


def test_generation_strictly_increases_across_calls(adapter, fake_native_host):
    adapter.render_historical_data(_CANDLES)
    adapter.render_historical_volume(_VOLUMES)
    first_generation = fake_native_host.submit_ohlcv.call_args.kwargs["generation"]

    adapter.add_overlay_indicator("ema", "#ffffff")
    adapter.update_indicator_data("ema", [1.0], [1.0])
    second_generation = fake_native_host.submit_indicators.call_args.kwargs[
        "generation"
    ]

    assert second_generation > first_generation

"""Unit tests for BOT-098F6B's pure conversion/fencing logic.

No QApplication is needed for any of this — snapshot packing and marker/
indicator conversion are plain Python over `QByteArray`/dataclasses. The
QQuickWidget host construction itself is sanity-level
(tests/sanity/test_native_backtest_chart_host_sanity.py), since it needs the
real theme/import bootstrap `create_quick_widget()`-style code depends on.
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QThread

from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_marker_snapshot import (
    NativeChartMarkerDirection,
    NativeChartMarkerKind,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_snapshot import (
    pack_native_ohlcv_snapshot,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
    NativeBacktestChartHost,
    NativeChartSubmissionFence,
    build_native_indicator_series,
    build_native_marker,
    build_native_ohlcv_arrays,
    resolve_candle_index_for_timestamp_ms,
    timestamp_seconds_to_ms,
)

_CANDLES = [
    (1_700_000_000.0, 10.0, 12.0, 9.0, 11.0),
    (1_700_000_060.0, 11.0, 13.0, 10.0, 12.0),
    (1_700_000_120.0, 12.0, 14.0, 11.0, 13.0),
]
_VOLUMES = [
    (1_700_000_000.0, 100.0, True),
    (1_700_000_060.0, 200.0, True),
    (1_700_000_120.0, 150.0, False),
]
_CANDLE_TIMESTAMPS_MS = tuple(timestamp_seconds_to_ms(t) for t, *_ in _CANDLES)


def test_timestamp_seconds_to_ms_rounds_to_nearest_millisecond():
    assert timestamp_seconds_to_ms(1_700_000_000.0) == 1_700_000_000_000
    assert timestamp_seconds_to_ms(1_700_000_000.0009) == 1_700_000_000_001


def test_resolve_candle_index_exact_match_only():
    assert (
        resolve_candle_index_for_timestamp_ms(
            _CANDLE_TIMESTAMPS_MS, _CANDLE_TIMESTAMPS_MS[1]
        )
        == 1
    )
    assert (
        resolve_candle_index_for_timestamp_ms(
            _CANDLE_TIMESTAMPS_MS, _CANDLE_TIMESTAMPS_MS[1] + 1
        )
        is None
    )
    assert resolve_candle_index_for_timestamp_ms((), 0) is None


class TestBuildNativeOhlcvArrays:
    def test_happy_path_merges_candles_and_volume(self):
        timestamps, opens, _highs, _lows, _closes, volumes = build_native_ohlcv_arrays(
            _CANDLES, _VOLUMES
        )
        assert timestamps == _CANDLE_TIMESTAMPS_MS
        assert opens == (10.0, 11.0, 12.0)
        assert volumes == (100.0, 200.0, 150.0)

    def test_rejects_candle_volume_length_mismatch(self):
        with pytest.raises(ValueError, match="equal length"):
            build_native_ohlcv_arrays(_CANDLES, _VOLUMES[:-1])

    def test_rejects_misaligned_candle_volume_timestamps(self):
        bad_volumes = [*_VOLUMES[:-1], (1_700_000_121.0, 150.0, False)]
        with pytest.raises(ValueError, match="must be aligned"):
            build_native_ohlcv_arrays(_CANDLES, bad_volumes)

    def test_duplicate_or_non_monotonic_converted_timestamps_are_rejected_downstream(
        self,
    ):
        """build_native_ohlcv_arrays itself only converts units; the one
        source of truth for strict-monotonic timestamps is the packer it
        feeds — this proves that contract survives the conversion step."""
        duplicate_candles = [_CANDLES[0], _CANDLES[0], _CANDLES[2]]
        duplicate_volumes = [_VOLUMES[0], _VOLUMES[0], _VOLUMES[2]]
        timestamps, opens, highs, lows, closes, volumes = build_native_ohlcv_arrays(
            duplicate_candles, duplicate_volumes
        )
        with pytest.raises(ValueError, match="increase strictly"):
            pack_native_ohlcv_snapshot(
                revision=1,
                timestamps=timestamps,
                opens=opens,
                highs=highs,
                lows=lows,
                closes=closes,
                volumes=volumes,
            )


class TestBuildNativeIndicatorSeries:
    def test_dense_happy_path(self):
        x_data = [_CANDLES[0][0], _CANDLES[1][0], _CANDLES[2][0]]
        y_data = [1.0, 2.0, 3.0]
        series = build_native_indicator_series(
            _CANDLE_TIMESTAMPS_MS, x_data, y_data, rgba=0xFF00BFFF
        )
        assert series.values == (1.0, 2.0, 3.0)
        assert series.rgba == 0xFF00BFFF

    def test_forward_fills_a_gap_after_the_first_sample(self):
        x_data = [_CANDLES[0][0], _CANDLES[2][0]]
        y_data = [1.0, 3.0]
        series = build_native_indicator_series(
            _CANDLE_TIMESTAMPS_MS, x_data, y_data, rgba=0xFF00BFFF
        )
        assert series.values == (1.0, 1.0, 3.0)

    def test_backfills_a_leading_gap_from_the_first_sample(self):
        x_data = [_CANDLES[1][0], _CANDLES[2][0]]
        y_data = [2.0, 3.0]
        series = build_native_indicator_series(
            _CANDLE_TIMESTAMPS_MS, x_data, y_data, rgba=0xFF00BFFF
        )
        assert series.values == (2.0, 2.0, 3.0)

    def test_skips_non_finite_values(self):
        x_data = [_CANDLES[0][0], _CANDLES[1][0], _CANDLES[2][0]]
        y_data = [1.0, float("nan"), 3.0]
        series = build_native_indicator_series(
            _CANDLE_TIMESTAMPS_MS, x_data, y_data, rgba=0xFF00BFFF
        )
        assert series.values == (1.0, 1.0, 3.0)

    def test_skips_unaligned_indicator_timestamps(self):
        x_data = [_CANDLES[0][0], _CANDLES[0][0] + 5.0]
        y_data = [1.0, 2.0]
        series = build_native_indicator_series(
            _CANDLE_TIMESTAMPS_MS, x_data, y_data, rgba=0xFF00BFFF
        )
        assert series.values == (1.0, 1.0, 1.0)

    def test_x_and_y_length_mismatch_is_rejected(self):
        with pytest.raises(ValueError, match="equal length"):
            build_native_indicator_series(
                _CANDLE_TIMESTAMPS_MS, [1.0], [1.0, 2.0], rgba=1
            )


class TestBuildNativeMarker:
    def test_truthful_long_entry_and_exit_conversion(self):
        entry = build_native_marker(
            (_CANDLES[0][0], 10.5, "MUA (LONG)", "#26a69a", "up"),
            _CANDLE_TIMESTAMPS_MS,
        )
        assert entry.candle_index == 0
        assert entry.kind is NativeChartMarkerKind.LONG_ENTRY
        assert entry.direction is NativeChartMarkerDirection.UP
        assert entry.rgba == 0xFF26A69A

        exit_marker = build_native_marker(
            (_CANDLES[1][0], 12.5, "ĐÓNG LONG", "#ef5350", "down"),
            _CANDLE_TIMESTAMPS_MS,
        )
        assert exit_marker.candle_index == 1
        assert exit_marker.kind is NativeChartMarkerKind.LONG_EXIT
        assert exit_marker.direction is NativeChartMarkerDirection.DOWN

    def test_rejects_an_unaligned_marker_timestamp(self):
        with pytest.raises(ValueError, match="does not align"):
            build_native_marker(
                (_CANDLES[0][0] + 1.0, 10.5, "MUA (LONG)", "#26a69a", "up"),
                _CANDLE_TIMESTAMPS_MS,
            )

    def test_rejects_an_unrecognized_label(self):
        with pytest.raises(ValueError, match="no native semantic mapping"):
            build_native_marker(
                (_CANDLES[0][0], 10.5, "???", "#26a69a", "up"),
                _CANDLE_TIMESTAMPS_MS,
            )

    def test_rejects_an_unrecognized_direction(self):
        with pytest.raises(ValueError, match="not supported"):
            build_native_marker(
                (_CANDLES[0][0], 10.5, "MUA (LONG)", "#26a69a", "sideways"),
                _CANDLE_TIMESTAMPS_MS,
            )


class TestNativeChartSubmissionFence:
    def test_admits_strictly_increasing_generation_within_the_same_action(self):
        fence = NativeChartSubmissionFence()
        assert fence.admit(action_id=1, generation=0) is True
        assert fence.admit(action_id=1, generation=1) is True

    def test_rejects_a_stale_or_repeated_token(self):
        fence = NativeChartSubmissionFence()
        assert fence.admit(action_id=2, generation=3) is True
        assert fence.admit(action_id=2, generation=3) is False
        assert fence.admit(action_id=2, generation=2) is False
        assert fence.admit(action_id=1, generation=99) is False

    def test_admits_a_new_action_id_even_with_generation_reset_to_zero(self):
        fence = NativeChartSubmissionFence()
        assert fence.admit(action_id=1, generation=5) is True
        assert fence.admit(action_id=2, generation=0) is True


class TestNativeBacktestChartHostSubmit:
    def test_submit_markers_skips_out_of_range_markers_without_error(self):
        widget = MagicMock()
        widget.thread.return_value = QThread.currentThread()
        chart_item = MagicMock()
        chart_item.submitMarkerSnapshot.return_value = True
        host = NativeBacktestChartHost(
            widget=widget,
            component=MagicMock(),
            root_item=MagicMock(),
            chart_item=chart_item,
            gesture_bridge=MagicMock(),
            timezone_bridge=MagicMock(),
        )
        host._candle_timestamps_ms = _CANDLE_TIMESTAMPS_MS

        markers = [
            (1_600_000_000.0, 50.0, "MUA (LONG)", "#26a69a", "up"),  # Way in the past
            (_CANDLES[1][0], 12.5, "ĐÓNG LONG", "#ef5350", "down"),  # On candle 1
            (1_800_000_000.0, 60.0, "MUA (LONG)", "#26a69a", "up"),  # In the future
        ]
        assert host.submit_markers(markers, action_id=1, generation=0) is True
        assert chart_item.submitMarkerSnapshot.call_count == 1

    def test_submit_indicators_with_empty_or_warmup_series_succeeds(self):
        widget = MagicMock()
        widget.thread.return_value = QThread.currentThread()
        chart_item = MagicMock()
        chart_item.submitIndicatorSnapshot.return_value = True
        host = NativeBacktestChartHost(
            widget=widget,
            component=MagicMock(),
            root_item=MagicMock(),
            chart_item=chart_item,
            gesture_bridge=MagicMock(),
            timezone_bridge=MagicMock(),
        )
        host._candle_timestamps_ms = _CANDLE_TIMESTAMPS_MS

        series = [
            (
                0xFF00BFFF,
                [_CANDLES[1][0], _CANDLES[2][0]],
                [2.0, 3.0],
            )
        ]
        assert host.submit_indicators(series, action_id=1, generation=0) is True
        assert chart_item.submitIndicatorSnapshot.call_count == 1

from __future__ import annotations

from argparse import Namespace

from Sagittarius_Elite_Warrior.scripts.benchmarking.chart_migration_benchmark import (
    _CANDLE_COUNT,
    _INDICATOR_COUNT,
    _MARKER_COUNT,
    _VISIBLE_CANDLES,
    _WARMUP_UPDATES,
    _WINDOW_HEIGHT,
    _WINDOW_WIDTH,
    RendererBenchmarkResult,
    assert_benchmark_contract,
    build_report,
    comparison_speedup,
    make_argument_parser,
    make_standard_fixture,
    percentile_95,
    viewport_starts,
)


def _native_result() -> RendererBenchmarkResult:
    return RendererBenchmarkResult(
        backend="native",
        actual_backend="qt-quick-scene-graph",
        median_ms=8.0,
        p95_ms=12.0,
        updates_per_second=125.0,
        completed_captures=126,
        device_pixel_ratio=1.0,
        logical_resolution=f"{_WINDOW_WIDTH}x{_WINDOW_HEIGHT}",
        physical_width=_WINDOW_WIDTH,
        displayed_markers=25,
        represented_markers=31,
        crosshair_final_candle_index=_CANDLE_COUNT - _VISIBLE_CANDLES + 135,
        expected_crosshair_candle_index=_CANDLE_COUNT - _VISIBLE_CANDLES + 135,
        camera_geometry_retained={
            "ohlcv": True,
            "volume": True,
            "indicator": True,
            "marker": False,
        },
        pointer_geometry_retained={
            "ohlcv": True,
            "volume": True,
            "indicator": True,
            "marker": True,
        },
        renderer_diagnostics={"geometry_builds": 1},
        sampled_expected_colors={
            "#00c087": True,
            "#f6465d": True,
            "#00bfff": True,
            "#f0b90b": True,
        },
        qt_warnings=(),
    )


def _python_result() -> RendererBenchmarkResult:
    return RendererBenchmarkResult(
        backend="python",
        actual_backend="cpu",
        median_ms=40.0,
        p95_ms=65.0,
        updates_per_second=25.0,
        completed_captures=121,
        device_pixel_ratio=1.0,
        logical_resolution=f"{_WINDOW_WIDTH}x{_WINDOW_HEIGHT}",
        physical_width=_WINDOW_WIDTH,
        displayed_markers=25,
        represented_markers=31,
        crosshair_final_candle_index=None,
        expected_crosshair_candle_index=_CANDLE_COUNT - _VISIBLE_CANDLES + 75,
        camera_geometry_retained={
            "ohlcv": None,
            "volume": None,
            "indicator": None,
            "marker": None,
        },
        pointer_geometry_retained={
            "ohlcv": None,
            "volume": None,
            "indicator": None,
            "marker": None,
        },
        renderer_diagnostics={"range_applies": 120},
        sampled_expected_colors={
            "#00c087": True,
            "#f6465d": True,
            "#00bfff": True,
            "#f0b90b": True,
        },
        qt_warnings=(),
    )


def _report() -> dict[str, object]:
    fixture = make_standard_fixture()
    return build_report(
        app=Namespace(platformName=lambda: "offscreen"),
        fixture=fixture,
        results=(_python_result(), _native_result()),
    )


def test_standard_fixture_has_one_shared_complete_renderer_payload():
    fixture = make_standard_fixture()

    assert len(fixture.candles) == _CANDLE_COUNT
    assert len(fixture.volumes) == _CANDLE_COUNT
    assert len(fixture.indicators) == _INDICATOR_COUNT
    assert len(fixture.markers) == _MARKER_COUNT
    assert len({marker.kind for marker in fixture.markers}) == 2
    assert fixture.markers[0].label == "MUA (LONG)"
    assert fixture.markers[1].label == "ĐÓNG LONG"
    assert fixture.candles[1][0] - fixture.candles[0][0] == 60.0
    assert all(
        len(indicator.values) == _CANDLE_COUNT for indicator in fixture.indicators
    )


def test_viewport_sequence_is_deterministic_and_remains_in_fixture_bounds():
    starts = viewport_starts(
        candle_count=_CANDLE_COUNT,
        visible_candles=_VISIBLE_CANDLES,
        update_count=4,
    )

    assert starts == (0, 37, 74, 111)
    assert all(start + _VISIBLE_CANDLES <= _CANDLE_COUNT for start in starts)


def test_percentile_95_uses_nearest_rank_contract():
    assert percentile_95([8.0, 1.0, 6.0, 3.0, 5.0]) == 8.0


def test_both_backend_report_computes_speedup_without_a_timing_threshold():
    speedup = comparison_speedup((_python_result(), _native_result()))

    assert speedup == 5.0
    passed, message = assert_benchmark_contract(
        _report(), require_native_retained_geometry=True
    )
    assert passed is True, message


def test_ci_contract_rejects_native_pointer_geometry_rebuild():
    report = _report()
    results = report["results"]
    assert isinstance(results, list)
    native = next(item for item in results if item["backend"] == "native")
    native["pointer_geometry_retained"]["marker"] = False

    passed, message = assert_benchmark_contract(
        report, require_native_retained_geometry=True
    )

    assert passed is False
    assert "marker geometry" in message


def test_desktop_contract_requires_actual_visual_semantic_evidence():
    report = _report()
    results = report["results"]
    assert isinstance(results, list)
    results[0]["sampled_expected_colors"]["#f6465d"] = False

    passed, message = assert_benchmark_contract(
        report,
        require_desktop_visuals=True,
        require_native_retained_geometry=True,
    )

    assert passed is False
    assert "#f6465d" in message


def test_cli_exposes_ci_and_desktop_contract_modes():
    arguments = make_argument_parser().parse_args(
        ["--backend", "both", "--ci-contract", "--desktop-contract"]
    )

    assert arguments.backend == "both"
    assert arguments.ci_contract is True
    assert arguments.desktop_contract is True
    assert arguments.warmup_updates == _WARMUP_UPDATES

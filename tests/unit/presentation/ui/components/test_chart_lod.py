import math

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_lod import (
    aggregate_ohlc_bucket,
    aggregate_volume_bucket,
    build_ohlc_lod_pyramid,
    lod_slice_indices,
    select_lod_level,
)


def test_ohlc_bucket_preserves_business_extremes_and_boundary_prices():
    rows = [
        (1000.0, 100.0, 108.0, 95.0, 104.0),
        (1060.0, 104.0, 115.0, 101.0, 110.0),
        (1120.0, 110.0, 112.0, 90.0, 92.0),
    ]

    bucket = aggregate_ohlc_bucket(rows)

    assert bucket == (1060.0, 100.0, 115.0, 90.0, 92.0)


def test_volume_bucket_preserves_total_volume():
    rows = [(1000.0, 10.0, True), (1060.0, 12.0, False), (1120.0, 8.0, True)]

    bucket = aggregate_volume_bucket(rows)

    assert bucket == (1060.0, 30.0, True)


def test_lod_level_is_a_bounded_power_of_two_pixel_budget():
    assert select_lod_level(150, 1500.0, available_levels=14) == 0
    assert select_lod_level(6420, 1500.0, available_levels=14) == 4
    assert select_lod_level(6420, 1500.0, available_levels=3) == 2


def test_ohlc_pyramid_preserves_global_extremes_at_coarsest_level():
    rows = [
        (float(index * 60), 100.0 + index, 110.0 + index, 90.0 - index, 105.0)
        for index in range(9)
    ]

    pyramid = build_ohlc_lod_pyramid(rows)
    coarsest = pyramid[-1][0]

    assert len(pyramid) == 5
    assert coarsest[1] == rows[0][1]
    assert coarsest[2] == max(row[2] for row in rows)
    assert coarsest[3] == min(row[3] for row in rows)
    assert coarsest[4] == rows[-1][4]


def test_lod_slice_rounds_outward_to_include_partial_edge_buckets():
    lo, hi = lod_slice_indices(9, 33, level=3)

    assert (lo, hi) == (1, 5)
    assert math.prod((hi - lo, 8)) >= 33 - 9


def _candles(count: int):
    return [
        (
            float(index * 60),
            100.0 + index,
            110.0 + index,
            90.0 - index,
            105.0 + index,
        )
        for index in range(count)
    ]


def test_candlestick_uses_lod_only_when_samples_exceed_pixel_budget(qapp):
    card = ChartCard("BTCUSDT")
    card.resize(400, 300)
    card.show()
    rows = _candles(4096)
    card.render_historical_data(rows)
    card.plot_layout.main_plot.setXRange(rows[0][0], rows[-1][0], padding=0)
    qapp.processEvents()

    rendered, _width, _signature = card.candlestick._visible_render_slice()

    assert card.candlestick.last_render_lod_level > 0
    assert len(rendered) < len(rows)
    assert min(row[3] for row in rendered) == min(row[3] for row in rows)
    assert max(row[2] for row in rendered) == max(row[2] for row in rows)

    card.plot_layout.main_plot.setXRange(rows[100][0], rows[120][0], padding=0)
    qapp.processEvents()
    card.candlestick._visible_render_slice()

    assert card.candlestick.last_render_lod_level == 0
    card.cleanup()


def test_volume_lod_preserves_sum_while_reducing_rendered_bars(qapp):
    card = ChartCard("BTCUSDT")
    card.resize(400, 300)
    card.show()
    rows = [
        (float(index * 60), float(index + 1), index % 2 == 0) for index in range(4096)
    ]
    card.render_historical_volume(rows)
    card.volume.refresh_window(rows[0][0], rows[-1][0])
    qapp.processEvents()

    applied_heights = card.volume.graphics_item.opts["height"]
    assert card.volume.last_applied_lod_level > 0
    assert card.volume.last_applied_bar_count < len(rows)
    assert math.isclose(sum(applied_heights), sum(row[1] for row in rows))
    card.cleanup()

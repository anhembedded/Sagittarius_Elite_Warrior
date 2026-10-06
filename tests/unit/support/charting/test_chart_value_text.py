"""`EPIC-033N` — the chart's crosshair, price tag, marker tooltip and
indicator legend write every number and time through `AppValueFormatter`
(`ui-presentation-rule.md`): the text a label shows is what the formatter
writes for that kind, so a price reads the same on the chart as in a table.
"""

from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.price_line import (
    LastPriceLine,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    AppValueFormatter,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind, FormatContext

_CANDLE = (1_751_328_000.0, 64_250.1, 64_999.999, 0.00001234, 65_000.0)


@pytest.fixture
def readouts(qapp):
    card = ChartCard("BTCUSDT")
    shown: list[str] = []
    card.crosshair._on_readout = shown.append
    return card, shown


def _price(value: float) -> str:
    return write_value(ColumnKind.PRICE, value)


def test_the_candle_readout_is_the_formatters_price_percent_and_timestamp(readouts):
    card, shown = readouts
    t, o, h, low, c = _CANDLE

    card.crosshair._update_ohlc_label(_CANDLE)

    moment = datetime.fromtimestamp(t, tz=UTC)
    assert shown == [
        (
            f"{write_value(ColumnKind.TIMESTAMP, moment)}"
            f"   O {_price(o)}   H {_price(h)}   L {_price(low)}   C {_price(c)}"
            f"   ({write_value(ColumnKind.PERCENT, (c - o) / o * 100.0)})"
        )
    ]
    assert "O 64,250.10" in shown[0]
    assert "L 0.00001234" in shown[0]
    assert "(1.17%)" in shown[0]


def test_a_losing_candle_carries_its_minus(readouts):
    card, shown = readouts

    card.crosshair._update_ohlc_label((0.0, 100.0, 100.0, 90.0, 95.0))

    assert shown[0].endswith("(-5.00%)")


def test_the_value_readout_is_the_formatters_price(readouts):
    card, shown = readouts

    card.crosshair._update_label(1_751_328_000.0, 1234.5678)

    assert shown[0].endswith("Value: 1,234.57")


def test_the_crosshair_time_follows_the_chosen_display_zone(readouts):
    card, shown = readouts
    card.set_display_timezone("Asia/Ho_Chi_Minh")

    card.crosshair._update_label(1_751_328_000.0, 1.0)

    expected = AppValueFormatter("Asia/Ho_Chi_Minh").format(
        ColumnKind.TIMESTAMP,
        datetime.fromtimestamp(1_751_328_000.0, tz=UTC),
        FormatContext("timestamp"),
    )
    assert shown[0].startswith(f"Time: {expected}")
    assert "2025-07-01 07:00:00" in shown[0]


def test_a_time_no_datetime_can_hold_is_an_empty_text(readouts):
    card, shown = readouts

    card.crosshair._update_label(1e30, 1.0)

    assert shown[0].startswith("Time:    Value")


def test_the_last_price_tag_shows_the_formatters_price(qapp):
    card = ChartCard("BTCUSDT")
    line = LastPriceLine(card.plot_layout.main_plot)

    line.update_price(64_250.1, is_bullish=True)
    assert line._line.label.textItem.toPlainText() == "64,250.10"

    line.update_price(0.00001234, is_bullish=False)
    assert line._line.label.textItem.toPlainText() == "0.00001234"


def test_the_indicator_legend_shows_the_formatters_price(qapp):
    card = ChartCard("BTCUSDT")
    card.add_overlay_indicator("SMA_20", color="#f39c12")

    card.update_indicator_data("SMA_20", [1000.0, 1060.0], [50.0, 64_250.1])

    assert card.indicators._legend_labels["SMA_20"].text == (
        f"SMA_20: {_price(64_250.1)}"
    )
    assert card.indicators._legend_labels["SMA_20"].text == "SMA_20: 64,250.10"


def test_a_marker_tooltip_shows_the_formatters_price(qapp):
    card = ChartCard("BTCUSDT")

    card.set_script_markers("ema_cross", [(1000.0, 0.00001234, "Buy", "#0ECB81", "up")])

    item = card.indicators._marker_layer._items["ema_cross"][0]
    assert item.toolTip() == f"Buy @ {_price(0.00001234)}"
    assert item.toolTip() == "Buy @ 0.00001234"

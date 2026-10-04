"""`EPIC-029G` — `PriceLevelLayer`: keyed horizontal lines and bands attached
to a real `ChartCard`'s price plot from outside the card."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.price_level_layer import (
    LineStyle,
    PriceBand,
    PriceLevel,
    PriceLevelLayer,
)


def _layer(qapp) -> tuple[PriceLevelLayer, ChartCard]:
    card = ChartCard("BTCUSDT")
    return PriceLevelLayer(card.plot_layout.main_plot), card


def _on_plot(card: ChartCard, item: object) -> bool:
    return item in card.plot_layout.main_plot.items


def test_levels_are_drawn_on_the_cards_price_plot(qapp) -> None:
    layer, card = _layer(qapp)

    layer.set_levels(
        "grid",
        [
            PriceLevel(61000.0, "#26a69a", LineStyle.DASH, "L1"),
            PriceLevel(59000.0, "#ef5350", LineStyle.SOLID, "L0"),
        ],
    )

    lines = layer.line_items("grid")
    assert [line.value() for line in lines] == [59000.0, 61000.0]
    assert all(line.angle == 0 for line in lines)
    assert all(_on_plot(card, line) for line in lines)
    assert lines[1].label.format == "L1"


def test_setting_a_key_again_replaces_its_lines_and_no_other(qapp) -> None:
    layer, card = _layer(qapp)
    layer.set_levels("grid", [PriceLevel(59000.0, "#26a69a")])
    layer.set_levels("exits", [PriceLevel(55000.0, "#ef5350", label="SL")])
    old = layer.line_items("grid")[0]

    layer.set_levels("grid", [PriceLevel(60000.0, "#26a69a")])

    assert [line.value() for line in layer.line_items("grid")] == [60000.0]
    assert not _on_plot(card, old)
    assert [line.value() for line in layer.line_items("exits")] == [55000.0]


def test_a_clear_leaves_nothing_behind(qapp) -> None:
    layer, card = _layer(qapp)
    layer.set_levels("grid", [PriceLevel(59000.0, "#26a69a")])
    layer.set_bands("grid", [PriceBand(58000.0, 62000.0, "#888888")])
    drawn = [*layer.line_items("grid"), *layer.band_items("grid")]

    layer.clear("grid")

    assert layer.line_items("grid") == ()
    assert layer.band_items("grid") == ()
    assert not any(_on_plot(card, item) for item in drawn)


def test_a_band_spans_its_two_prices_horizontally(qapp) -> None:
    layer, _card = _layer(qapp)

    layer.set_bands("atr", [PriceBand(58000.0, 62000.0, "#888888", 0.2)])

    (band,) = layer.band_items("atr")
    assert tuple(band.getRegion()) == (58000.0, 62000.0)
    assert band.orientation == "horizontal"


def test_a_level_without_a_label_draws_none(qapp) -> None:
    layer, _card = _layer(qapp)

    layer.set_levels("grid", [PriceLevel(59000.0, "#26a69a")])

    assert not hasattr(layer.line_items("grid")[0], "label")

"""The chart's chrome takes `QPalette` roles and follows a palette change
(`EPIC-033G`)."""

from PySide6.QtGui import QColor, QPalette
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.chart_chrome import (
    ChartChrome,
)

_ROLE = QPalette.ColorRole


def _distinct_palette() -> QPalette:
    """A palette whose every chrome role has its own colour, none Qt's default."""
    palette = QPalette()
    for role, color in (
        (_ROLE.Base, "#102030"),
        (_ROLE.Text, "#a0b0c0"),
        (_ROLE.PlaceholderText, "#405060"),
        (_ROLE.ToolTipBase, "#708090"),
        (_ROLE.ToolTipText, "#d0e0f0"),
        (_ROLE.Window, "#203040"),
    ):
        palette.setColor(role, QColor(color))
    return palette


def test_each_chrome_colour_comes_from_its_role(qapp):
    chrome = ChartChrome.from_palette(_distinct_palette())

    assert chrome.background == QColor("#102030")
    assert chrome.foreground == QColor("#a0b0c0")
    assert chrome.crosshair == QColor("#405060")
    assert chrome.tag_fill == QColor("#708090")
    assert chrome.tag_text == QColor("#d0e0f0")
    assert chrome.uncovered == QColor("#203040")


def test_a_palette_change_repaints_background_axes_grid_and_crosshair(qapp):
    card = ChartCard("BTCUSDT")
    layout = card.plot_layout
    sub_plot = layout.add_subplot()

    layout.widget.setPalette(_distinct_palette())

    assert layout.widget.backgroundBrush().color() == QColor("#102030")
    for plot in (layout.main_plot, sub_plot):
        for axis_name in ("left", "bottom"):
            axis = plot.getAxis(axis_name)
            # The grid is drawn with the axis pen at `GRID_ALPHA`, so the
            # axis pen is the grid's colour too.
            assert axis.pen().color() == QColor("#a0b0c0")
            assert axis.textPen().color() == QColor("#a0b0c0")
    # A script's info panel writes uncoloured fields in the label's colour.
    card.plot_layout.script_info_label.setText("Trend: UP")
    assert "#a0b0c0" in card.plot_layout.script_info_label.item.toHtml()
    crosshair = card.crosshair
    assert crosshair._v_lines[0].pen.color() == QColor("#405060")
    assert crosshair._x_labels[0].fill.color() == QColor("#708090")
    assert crosshair._x_labels[0].color == QColor("#d0e0f0")
    card.cleanup()


def test_a_subplot_added_later_takes_the_current_chrome(qapp):
    card = ChartCard("BTCUSDT")
    layout = card.plot_layout
    layout.widget.setPalette(_distinct_palette())

    sub_plot = layout.add_subplot()

    assert sub_plot.getAxis("left").pen().color() == QColor("#a0b0c0")
    card.cleanup()

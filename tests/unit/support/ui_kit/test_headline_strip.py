"""`EPIC-043D` — the headline strip shows its figures larger than the detail, derived from the
platform's font, with the tone the meaning table gave each."""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase, QGuiApplication, QPalette
from Sagittarius_Elite_Warrior.src.support.ui_kit.headline_strip import (
    HEADLINE_SCALE,
    HeadlineFigure,
    HeadlineStrip,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

_EQUITY = HeadlineFigure(
    "equity", "Account value (USDT)", "1,000.00", kind=ColumnKind.MONEY
)
_PNL = HeadlineFigure(
    "pnl", "Unrealized PnL (USDT)", "▲ +12.50", Tone.POSITIVE, ColumnKind.MONEY
)
_WORDS = HeadlineFigure("positions", "Open positions", "3")


def _strip(qtbot) -> HeadlineStrip:
    strip = HeadlineStrip()
    qtbot.addWidget(strip)
    return strip


def test_a_strip_with_no_figure_is_not_shown(qtbot) -> None:
    strip = _strip(qtbot)

    strip.show_figures(())

    assert strip.isHidden()
    assert strip.keys == ()


def test_the_figures_are_shown_in_the_order_given_with_their_text(qtbot) -> None:
    strip = _strip(qtbot)

    strip.show_figures((_EQUITY, _PNL, _WORDS))

    assert strip.keys == ("equity", "pnl", "positions")
    assert [strip.text_of(key) for key in strip.keys] == ["1,000.00", "▲ +12.50", "3"]
    assert not strip.isHidden()


def test_a_figure_that_is_not_given_any_more_is_gone(qtbot) -> None:
    strip = _strip(qtbot)
    strip.show_figures((_EQUITY, _PNL))

    strip.show_figures((_EQUITY,))

    assert strip.keys == ("equity",)
    assert strip.text_of("pnl") is None


def test_the_same_figures_again_update_in_place(qtbot) -> None:
    strip = _strip(qtbot)
    strip.show_figures((_EQUITY,))
    label = strip.cell_value("equity")

    strip.show_figures((HeadlineFigure("equity", "Account value (USDT)", "2,000.00"),))

    assert strip.cell_value("equity") is label
    assert strip.text_of("equity") == "2,000.00"


def test_a_figure_is_larger_and_bolder_than_its_caption_in_the_platforms_family(
    qtbot,
) -> None:
    strip = _strip(qtbot)
    strip.show_figures((_WORDS,))
    cell = strip.cell_value("positions")
    caption = cell.parent().findChild(type(cell), "headline::positions::caption")

    assert cell.font().bold() and not caption.font().bold()
    assert (
        cell.font().pointSizeF() >= caption.font().pointSizeF() * HEADLINE_SCALE - 0.01
    )
    assert cell.font().family() == caption.font().family()


def test_a_money_figure_is_in_the_platforms_fixed_pitch_font(qtbot) -> None:
    strip = _strip(qtbot)
    strip.show_figures((_EQUITY, _WORDS))

    money = strip.cell_value("equity").font()
    words = strip.cell_value("positions").font()

    fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    assert money.family() == fixed.family()
    assert words.family() != "" and words.family() == strip.font().family()


def test_a_figure_takes_the_tone_the_meaning_table_gave_it_on_the_palette(
    qtbot,
) -> None:
    strip = _strip(qtbot)
    palette = QGuiApplication.palette()

    strip.show_figures((_EQUITY, _PNL))

    pnl, equity = strip.cell_value("pnl"), strip.cell_value("equity")
    assert pnl.palette().color(pnl.foregroundRole()) == tone_colour(
        Tone.POSITIVE, palette
    )
    assert equity.palette().color(equity.foregroundRole()) == QPalette().color(
        equity.foregroundRole()
    )


def test_a_figure_that_loses_its_tone_returns_to_the_platforms_colour(qtbot) -> None:
    strip = _strip(qtbot)
    strip.show_figures((_PNL,))

    strip.show_figures((HeadlineFigure("pnl", "Unrealized PnL (USDT)", "0.00"),))

    label = strip.cell_value("pnl")
    assert label.palette().color(label.foregroundRole()) == QPalette().color(
        label.foregroundRole()
    )


def test_a_figure_is_text_never_markup(qtbot) -> None:
    strip = _strip(qtbot)

    strip.show_figures((HeadlineFigure("x", "<b>caption</b>", "<i>1</i>"),))

    assert strip.text_of("x") == "<i>1</i>"

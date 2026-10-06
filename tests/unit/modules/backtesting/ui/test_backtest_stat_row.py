"""`BacktestStatRow` — the performance figures, as one read-out.

## Restated from two suites the gate has never run

`StatCardRowVM` had 8 tests and `StatCardRow.qml` had 5, and they lived at
`src/presentation/ui/qml/StatCardRow/tests/` — inside `src/`, which the gate's
`pytest tests` never collects. That is `CS-004` exactly, and `BUG-128` is what
it costs when nobody notices; so these are written here, where the gate runs
them, rather than moved.

Both suites' promises are the same sentences against a widget instead of a
`QVariantList`: a row per figure with a stable name, the live source re-read on
every refresh, zero figures rendering nothing, a missing unit or badge coming
out absent rather than as `"None"`, and a tone that is not a `Tone` falling back
to no verdict instead of raising. Two are gone with their subject — the QML
root loading and naming itself, and the lowercase `"positive"`/`"negative"`
strings `StatCard.qml` compared against, which existed only because a `.qml`
file cannot read a Python enum.

Since `EPIC-033N` the figures are raw values with a kind and the shown text is
`AppValueFormatter`'s: these assert what the person reads, through the formatter.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_stat_row import (
    BacktestStatRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import ratio_key
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind


def _card(**overrides: object) -> dict[str, object]:
    card: dict[str, object] = {
        "key": "net_pnl",
        "title": "Net profit",
        "figure": 1234.0,
        "kind": ColumnKind.MONEY,
        "suffix": "USDT",
        "valueTone": Tone.POSITIVE,
        "badgeTitle": "Net profit (%)",
        "badgeFigure": 12.3,
        "badgeKind": ColumnKind.PERCENT,
        "badgeTone": Tone.POSITIVE,
    }
    card.update(overrides)
    return card


def _cards(*titles: str) -> list[dict[str, object]]:
    return [
        _card(key=f"card{index}", title=title) for index, title in enumerate(titles)
    ]


@pytest.fixture
def source():
    return {"cards": [_card()]}


@pytest.fixture
def row(qapp, source):
    built = BacktestStatRow(lambda: source["cards"])
    yield built
    built.deleteLater()


def _label(row: BacktestStatRow, key: str) -> QLabel:
    label = row.readout.value_label(key)
    assert label is not None
    return label


def test_one_row_per_figure_and_its_badge_with_stable_keys(qapp, source, row):
    source["cards"] = _cards("A", "B", "C")
    row.refresh()

    assert row.readout.keys == (
        "card0",
        "card0.badge",
        "card1",
        "card1.badge",
        "card2",
        "card2.badge",
    )


def test_a_figure_is_written_by_the_formatter_with_its_unit_in_the_title(row):
    assert row.readout.value_text("net_pnl") == "1,234.00"
    assert row.readout.value_text("net_pnl.badge") == "12.30%"
    form = row.findChildren(QLabel)
    assert "Net profit (USDT)" in [label.text() for label in form]
    assert "Net profit (%)" in [label.text() for label in form]


def test_a_card_without_a_unit_or_a_badge_has_neither_row_nor_the_word_none(
    qapp, source, row
):
    source["cards"] = [
        {"key": "trades", "title": "Trades", "figure": 42, "kind": ColumnKind.QUANTITY}
    ]
    row.refresh()

    assert row.readout.keys == ("trades",)
    assert row.readout.value_text("trades") == "42"
    assert "Trades" in [label.text() for label in row.findChildren(QLabel)]


def test_a_ratio_is_two_decimals_and_infinity_reads_as_the_symbol(qapp, source, row):
    source["cards"] = [
        _card(
            key=ratio_key("profit_factor"),
            figure=float("inf"),
            kind=ColumnKind.QUANTITY,
            badgeFigure=None,
        )
    ]
    row.refresh()

    assert row.readout.value_text(ratio_key("profit_factor")) == "\u221e"

    source["cards"] = [
        _card(
            key=ratio_key("profit_factor"),
            figure=1.8456,
            kind=ColumnKind.QUANTITY,
            badgeFigure=None,
        )
    ]
    row.refresh()

    assert row.readout.value_text(ratio_key("profit_factor")) == "1.85"


def test_zero_figures_renders_no_rows(qapp, source, row):
    source["cards"] = []
    row.refresh()

    assert row.readout.keys == ()


def test_every_refresh_re_reads_the_live_source(qapp, source, row):
    """The row holds a callback, not a copy — its caller says *when*, never
    what, which is what lets `_sync_stat_cards()` be the only scheduler."""
    assert row.readout.value_text("net_pnl") == "1,234.00"

    source["cards"] = [_card(figure=99.0, suffix="")]
    row.refresh()

    assert row.readout.value_text("net_pnl") == "99.00"


def test_a_refresh_replaces_the_previous_runs_figures(qapp, source, row):
    """Replaced, not appended to: a second run's numbers are not the first's,
    and this widget is constructed once per screen."""
    source["cards"] = _cards("A", "B")
    row.refresh()
    source["cards"] = _cards("C")
    row.refresh()

    assert row.readout.keys == ("card0", "card0.badge")
    assert "C (USDT)" in [label.text() for label in row.findChildren(QLabel)]


def _text_colour(label: QLabel) -> str:
    return label.palette().color(QPalette.ColorRole.WindowText).name()


def test_a_gain_and_a_loss_read_differently(qapp, source, row):
    """Green for gain and red for loss is a convention of this domain, which
    is why ADR D21's "colour only where it carries meaning" keeps it — as a
    colour on the one label that carries the figure."""
    source["cards"] = [
        _card(key="a", valueTone=Tone.POSITIVE),
        _card(key="b", valueTone=Tone.NEGATIVE),
    ]
    row.refresh()

    assert _text_colour(_label(row, "a")) != _text_colour(_label(row, "b"))


def test_a_neutral_figure_keeps_the_platforms_own_colour(qapp, source, row):
    source["cards"] = [
        _card(key="a", valueTone=Tone.NEUTRAL),
        _card(key="b", valueTone=Tone.POSITIVE),
    ]
    row.refresh()

    neutral = _label(row, "a")
    assert _text_colour(neutral) == _text_colour(QLabel())
    assert _text_colour(_label(row, "b")) != _text_colour(neutral)


def test_a_figure_that_loses_its_tone_gives_the_colour_back(qapp, source, row):
    """The form is kept while the rows stay the same, so a second run with the
    same rows must not leave the first run's green on a neutral figure."""
    source["cards"] = [_card(key="a", valueTone=Tone.POSITIVE)]
    row.refresh()
    toned = _text_colour(_label(row, "a"))

    source["cards"] = [_card(key="a", valueTone=Tone.NEUTRAL)]
    row.refresh()

    assert _text_colour(_label(row, "a")) != toned


def test_a_tone_that_is_not_a_tone_is_no_verdict_rather_than_a_crash(qapp, source, row):
    """A card dict is plain data from the Presenter, and a missing or wrong
    tone must render — the same fallback every version of this row has had."""
    source["cards"] = [
        _card(key="a", valueTone="positive", badgeTone=None),
        _card(key="b", valueTone=Tone.NEUTRAL, badgeTone=Tone.NEUTRAL),
    ]
    row.refresh()

    assert _text_colour(_label(row, "a")) == _text_colour(_label(row, "b"))


def test_the_row_carries_no_stylesheet_of_its_own(row):
    """§11.4's target state, asserted rather than assumed: every pixel except
    the two domain colours is the platform's theme."""
    assert row.styleSheet() == ""
    assert all(label.styleSheet() == "" for label in row.findChildren(QLabel))

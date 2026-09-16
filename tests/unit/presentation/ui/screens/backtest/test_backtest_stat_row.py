"""`BacktestStatRow` — the performance figures, as read-only tiles.

## Restated from two suites the gate has never run

`StatCardRowVM` had 8 tests and `StatCardRow.qml` had 5, and they lived at
`src/presentation/ui/qml/StatCardRow/tests/` — inside `src/`, which the gate's
`pytest tests` never collects. That is `CS-004` exactly, and `BUG-128` is what
it costs when nobody notices; so these are written here, where the gate runs
them, rather than moved.

Both suites' promises are the same sentences against a widget instead of a
`QVariantList`: a tile per figure with a stable name, the live source re-read on
every refresh, zero figures rendering nothing, a missing suffix or badge coming
out empty rather than as `"None"`, and a tone that is not a `Tone` falling back
to no verdict instead of raising. Two are gone with their subject — the QML
root loading and naming itself, and the lowercase `"positive"`/`"negative"`
strings `StatCard.qml` compared against, which existed only because a `.qml`
file cannot read a Python enum.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLabel, QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_stat_row import (
    BacktestStatRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone


def _card(**overrides: object) -> dict[str, object]:
    card: dict[str, object] = {
        "title": "Net profit",
        "value": "1,234",
        "suffix": " USDT",
        "valueTone": Tone.POSITIVE,
        "badgeText": "+12.3%",
        "badgeTone": Tone.POSITIVE,
    }
    card.update(overrides)
    return card


@pytest.fixture
def source():
    return {"cards": [_card()]}


@pytest.fixture
def row(qapp, source):
    built = BacktestStatRow(lambda: source["cards"])
    yield built
    built.deleteLater()


def _tiles(row: BacktestStatRow) -> list[QWidget]:
    return [
        child
        for child in row.findChildren(QWidget)
        if child.objectName().startswith("cardMetric_")
    ]


def _label(row: BacktestStatRow, name: str) -> QLabel | None:
    return row.findChild(QLabel, name)


def test_one_tile_per_figure_with_stable_names(qapp, source, row):
    source["cards"] = [_card(title="A"), _card(title="B"), _card(title="C")]
    row.refresh()

    assert [tile.objectName() for tile in _tiles(row)] == [
        "cardMetric_0",
        "cardMetric_1",
        "cardMetric_2",
    ]


def test_a_tile_shows_its_title_uppercased_and_its_value_with_the_suffix(row):
    assert _label(row, "cardMetricTitle_0").text() == "NET PROFIT"
    assert _label(row, "cardMetricValue_0").text() == "1,234 USDT"
    assert _label(row, "cardMetricBadge_0").text() == "+12.3%"


def test_a_missing_suffix_or_badge_is_empty_rather_than_the_word_none(
    qapp, source, row
):
    source["cards"] = [{"title": "Trades", "value": "42"}]
    row.refresh()

    assert _label(row, "cardMetricValue_0").text() == "42"
    assert _label(row, "cardMetricBadge_0") is None


def test_zero_figures_renders_no_tiles(qapp, source, row):
    source["cards"] = []
    row.refresh()

    assert _tiles(row) == []


def test_every_refresh_re_reads_the_live_source(qapp, source, row):
    """The row holds a callback, not a copy — its caller says *when*, never
    what, which is what lets `_sync_stat_cards()` be the only scheduler."""
    assert _label(row, "cardMetricValue_0").text() == "1,234 USDT"

    source["cards"] = [_card(value="99", suffix="")]
    row.refresh()

    assert _label(row, "cardMetricValue_0").text() == "99"


def test_a_refresh_replaces_the_previous_runs_figures(qapp, source, row):
    """Rebuilt, not appended to: a second run's numbers are not the first's,
    and this widget is constructed once per screen."""
    source["cards"] = [_card(title="A"), _card(title="B")]
    row.refresh()
    source["cards"] = [_card(title="C")]
    row.refresh()

    assert len(_tiles(row)) == 1
    assert _label(row, "cardMetricTitle_0").text() == "C"


def _text_colour(label: QLabel) -> str:
    return label.palette().color(QPalette.ColorRole.WindowText).name()


def test_a_gain_and_a_loss_read_differently(qapp, source, row):
    """Green for gain and red for loss is a convention of this domain, which
    is why ADR D21's "colour only where it carries meaning" keeps it — as a
    colour on the one label that carries the figure."""
    source["cards"] = [_card(valueTone=Tone.POSITIVE), _card(valueTone=Tone.NEGATIVE)]
    row.refresh()

    gain = _text_colour(_label(row, "cardMetricValue_0"))
    loss = _text_colour(_label(row, "cardMetricValue_1"))
    assert gain != loss


def test_a_neutral_figure_keeps_the_platforms_own_colour(qapp, source, row):
    source["cards"] = [_card(valueTone=Tone.NEUTRAL), _card(valueTone=Tone.POSITIVE)]
    row.refresh()

    neutral = _label(row, "cardMetricValue_0")
    toned = _label(row, "cardMetricValue_1")
    assert _text_colour(neutral) == _text_colour(_label(row, "cardMetricTitle_0"))
    assert _text_colour(toned) != _text_colour(neutral)


def test_a_tone_that_is_not_a_tone_is_no_verdict_rather_than_a_crash(qapp, source, row):
    """A card dict is plain data from the Presenter, and a missing or wrong
    tone must render — the same fallback every version of this row has had."""
    source["cards"] = [
        _card(valueTone="positive", badgeTone=None),
        _card(valueTone=Tone.NEUTRAL, badgeTone=Tone.NEUTRAL),
    ]
    row.refresh()

    assert _text_colour(_label(row, "cardMetricValue_0")) == _text_colour(
        _label(row, "cardMetricValue_1")
    )


def test_the_row_carries_no_stylesheet_of_its_own(row):
    """§11.4's target state, asserted rather than assumed: every pixel except
    the two domain colours is the platform's theme."""
    assert row.styleSheet() == ""
    assert all(tile.styleSheet() == "" for tile in _tiles(row))

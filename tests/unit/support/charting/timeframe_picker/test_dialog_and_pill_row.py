"""The two timeframe views, rendered for real — `EPIC-025` PR 4.3k.

## Restated from the deleted QML host's suite

`test_timeframe_picker_dialog_host.py` had 7 tests against
`TimeframePickerDialog` when it hosted `TimeframePicker.qml`. Six are restated
here against the `QTreeWidget` that replaced it — what an open seeds from, that
choosing closes with no Apply step, that Cancel emits nothing, that a pin writes
through to the host's store, that reopening picks up a changed current code, and
that a dialog built around an existing selection shares it verbatim. The
seventh, a broken `.qml` raising instead of rendering a blank box, has no
subject.

The pill row's own tests are new here: it had none of its own, because
`TimeframeToolbar.qml` was only ever exercised through `ChartToolbar`. Its
render behaviour is cheap to pin directly now that it is widgets, and
`test_chart_toolbar.py` keeps the wiring tests that need the real toolbar.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton
from Sagittarius_Elite_Warrior.src.support.charting.timeframe_picker import (
    PinnedTimeframes,
    TimeframePickerDialog,
    TimeframePillRow,
    TimeframeSelection,
)

_PIN_COLUMN = 2


class _Seed:
    """Stands in for a screen: the codes it offers and the one it is on, both
    changeable between opens the way a real screen's are."""

    def __init__(self, codes: list[str], current: str) -> None:
        self.codes = codes
        self.current = current


@pytest.fixture
def seed():
    return _Seed(codes=["1m", "5m", "1h", "4h", "1d"], current="1h")


@pytest.fixture
def pinned():
    return PinnedTimeframes(initial=["1m", "1h"])


@pytest.fixture
def dialog(qapp, seed, pinned):
    built = TimeframePickerDialog.from_callbacks(
        get_codes=lambda: seed.codes,
        get_current=lambda: seed.current,
        get_pinned=pinned.get,
        set_pinned=pinned.set,
    )
    yield built
    built.close()


# -- the dialog --------------------------------------------------------------


def test_opening_seeds_the_body_from_the_screens_current_codes(qapp, dialog, seed):
    dialog.open_dialog()
    qapp.processEvents()

    for code in seed.codes:
        assert dialog.item_for(code) is not None, code
    assert dialog._current.text() == "Current: 1h"


def test_a_code_the_screen_does_not_offer_is_not_in_the_body(qapp, dialog):
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog.item_for("1s") is None


def test_choosing_a_code_emits_and_closes_with_no_apply_step(qapp, dialog):
    """Every version of this widget has chosen and closed: there is no Apply,
    and Escape or the close control is how a caller backs out."""
    heard: list[str] = []
    dialog.chosen.connect(heard.append)
    dialog.open_dialog()
    qapp.processEvents()

    dialog._tree.itemActivated.emit(dialog.item_for("4h"), 0)
    qapp.processEvents()

    assert heard == ["4h"]
    assert not dialog.isVisible()


def test_clicking_a_group_heading_chooses_nothing(qapp, dialog):
    """A heading carries no code, so it is not a row — the state it would
    otherwise reach is "chose a group", which nothing downstream can read."""
    heard: list[str] = []
    dialog.chosen.connect(heard.append)
    dialog.open_dialog()
    qapp.processEvents()

    dialog._tree.itemClicked.emit(dialog._tree.topLevelItem(0), 0)
    qapp.processEvents()

    assert heard == []
    assert dialog.isVisible() is True


def test_cancel_closes_without_emitting(qapp, dialog):
    heard: list[str] = []
    dialog.chosen.connect(heard.append)
    dialog.open_dialog()
    qapp.processEvents()

    dialog.reject()
    qapp.processEvents()

    assert heard == []
    assert not dialog.isVisible()


def test_toggling_a_pin_writes_through_to_the_hosts_store(qapp, dialog, pinned):
    dialog.open_dialog()
    qapp.processEvents()

    dialog.item_for("4h").setCheckState(_PIN_COLUMN, Qt.CheckState.Checked)
    qapp.processEvents()

    assert "4h" in pinned.get()


def test_a_pin_does_not_close_the_dialog(qapp, dialog):
    """Pinning three intervals is a different act from choosing one, and
    closing on the first pin would make it impossible."""
    dialog.open_dialog()
    qapp.processEvents()

    dialog.item_for("4h").setCheckState(_PIN_COLUMN, Qt.CheckState.Checked)
    qapp.processEvents()

    assert dialog.isVisible() is True


def test_unticking_a_pin_writes_the_removal_through(qapp, dialog, pinned):
    dialog.open_dialog()
    qapp.processEvents()

    dialog.item_for("1m").setCheckState(_PIN_COLUMN, Qt.CheckState.Unchecked)
    qapp.processEvents()

    assert "1m" not in pinned.get()


def test_reopening_picks_up_a_changed_current_code(qapp, dialog, seed):
    """Built once and reused, so nothing may be captured at construction."""
    dialog.open_dialog()
    qapp.processEvents()
    dialog.close()

    seed.current = "1d"
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog._current.text() == "Current: 1d"


def test_reopening_picks_up_a_changed_option_list(qapp, dialog, seed):
    dialog.open_dialog()
    qapp.processEvents()
    dialog.close()

    seed.codes = ["1m", "1s"]
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog.item_for("1s") is not None
    assert dialog.item_for("4h") is None


def test_the_sub_minute_warning_appears_only_when_one_is_offered(qapp, dialog, seed):
    dialog.open_dialog()
    qapp.processEvents()
    assert dialog._warning.isVisibleTo(dialog) is False

    seed.codes = ["1s", "1m"]
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog._warning.isVisibleTo(dialog) is True


def test_built_around_an_existing_selection_it_shares_it_verbatim(qapp, seed, pinned):
    """`ChartToolbar`'s constructor: the dialog must read and write the very
    selection the pill row does, not a second one from the same callbacks."""
    selection = TimeframeSelection(
        get_codes=lambda: seed.codes,
        get_current=lambda: seed.current,
        get_pinned=pinned.get,
        set_pinned=pinned.set,
    )
    selection.refresh()

    built = TimeframePickerDialog(selection)

    assert built._selection is selection
    built.close()


# -- the pill row ------------------------------------------------------------


@pytest.fixture
def row(qapp, seed, pinned):
    selection = TimeframeSelection(
        get_codes=lambda: seed.codes,
        get_current=lambda: seed.current,
        get_pinned=pinned.get,
        set_pinned=pinned.set,
    )
    selection.refresh()
    built = TimeframePillRow(selection)
    built._selection_for_test = selection
    yield built
    built.deleteLater()


def test_the_row_shows_one_pill_per_pinned_code_in_order(row):
    assert [
        button.text()
        for button in row.findChildren(QPushButton)
        if button.objectName().startswith("timeframePill_")
    ] == ["1m", "1h"]


def test_the_current_pill_is_the_checked_one(row):
    assert row.button_for("1h").isChecked() is True
    assert row.button_for("1m").isChecked() is False


def test_clicking_a_pill_chooses_that_code(qapp, row):
    heard: list[str] = []
    row._selection_for_test.chosen.connect(heard.append)

    row.button_for("1m").click()
    qapp.processEvents()

    assert heard == ["1m"]


def test_seeding_the_current_pill_is_not_a_click(qapp, seed, pinned):
    """The checked pill is written at build time, and a check that read as a
    click would choose an interval nobody picked."""
    selection = TimeframeSelection(
        get_codes=lambda: seed.codes,
        get_current=lambda: seed.current,
        get_pinned=pinned.get,
        set_pinned=pinned.set,
    )
    selection.refresh()
    heard: list[str] = []
    selection.chosen.connect(heard.append)

    built = TimeframePillRow(selection)

    assert built.button_for("1h").isChecked() is True
    assert heard == []
    built.deleteLater()


def test_pinning_adds_a_pill_and_unpinning_removes_it(qapp, row):
    row._selection_for_test.toggle_pinned("4h")
    qapp.processEvents()
    assert row.button_for("4h") is not None

    row._selection_for_test.toggle_pinned("4h")
    qapp.processEvents()
    assert row.button_for("4h") is None


def test_the_more_button_only_asks_its_host_to_open_something(qapp, row):
    """Opening the full picker is a composition decision: this row emits and
    the host decides, because the host owns the dialog whose pinned set the
    row also reads."""
    heard: list[int] = []
    row.more_requested.connect(lambda: heard.append(1))

    row.findChild(QPushButton, "btnTimeframeMore").click()
    qapp.processEvents()

    assert heard == [1]

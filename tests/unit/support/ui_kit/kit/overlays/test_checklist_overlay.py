"""Tests for `kit.overlays.checklist_overlay.ChecklistOverlay` — `EPIC-025` PR 4.3f.

Restated from `CheckboxListVM`'s own suite, which went with `CheckboxList.qml`.
Everything that suite proved about *rendering state and reporting toggles* is
here, against real `QCheckBox`es; what it proved about `QVariantList` dict
shapes has no subject, because a row is a `ChecklistItem` now and a missing
field is a type error rather than a silent default.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    ChecklistItem,
    ChecklistOverlay,
    Overlay,
)


def _rows(overlay: ChecklistOverlay) -> list[str]:
    return [item.key for item in overlay.items]


def test_constructs_as_a_modal_overlay(qtbot):
    overlay = ChecklistOverlay("REFERENCE INDICATORS")
    qtbot.addWidget(overlay)

    assert isinstance(overlay, Overlay)
    assert overlay.isModal() is True
    assert overlay.items == ()


def test_set_items_renders_one_checkbox_each_in_order(qtbot):
    overlay = ChecklistOverlay("Title")
    qtbot.addWidget(overlay)

    overlay.set_items([ChecklistItem("ema", "EMA"), ChecklistItem("macd", "MACD")])

    assert _rows(overlay) == ["ema", "macd"]
    assert overlay.checkbox_for("ema").text() == "EMA"
    assert overlay.checkbox_for("macd").text() == "MACD"


def test_a_row_renders_its_checked_state(qtbot):
    overlay = ChecklistOverlay("Title")
    qtbot.addWidget(overlay)

    overlay.set_items([ChecklistItem("a", "A", checked=True), ChecklistItem("b", "B")])

    assert overlay.checkbox_for("a").isChecked() is True
    assert overlay.checkbox_for("b").isChecked() is False


def test_a_locked_row_is_disabled_rather_than_hidden(qtbot):
    """A locked row still says what it is — the behaviour both consuming
    dialogs have had since before either toolkit."""
    overlay = ChecklistOverlay("Title")
    qtbot.addWidget(overlay)

    overlay.set_items([ChecklistItem("fixed", "On bar close", locked=True)])

    box = overlay.checkbox_for("fixed")
    assert box.isVisible() is False  # never shown; the dialog is not open
    assert box.isEnabled() is False
    assert box.text() == "On bar close"


def test_a_tooltip_reaches_the_row_that_carries_a_cost(qtbot):
    overlay = ChecklistOverlay("Title")
    qtbot.addWidget(overlay)

    overlay.set_items(
        [ChecklistItem("tick", "Every tick", tooltip="Needs a 1-second sync")]
    )

    assert overlay.checkbox_for("tick").toolTip() == "Needs a 1-second sync"


def test_seeding_a_row_does_not_report_a_toggle(qtbot):
    """The rows arrive from a live model on every open, and a seed that read as
    a user's click would write the screen's own state back at it."""
    overlay = ChecklistOverlay("Title")
    qtbot.addWidget(overlay)
    seen: list[tuple[str, bool]] = []
    overlay.toggled.connect(lambda key, checked: seen.append((key, checked)))

    overlay.set_items([ChecklistItem("a", "A", checked=True)])
    overlay.set_items([ChecklistItem("a", "A", checked=False)])

    assert seen == []


def test_clicking_a_row_reports_its_key_and_new_state(qtbot):
    overlay = ChecklistOverlay("Title")
    qtbot.addWidget(overlay)
    overlay.set_items([ChecklistItem("a", "A"), ChecklistItem("b", "B")])

    with qtbot.waitSignal(overlay.toggled, timeout=1000) as blocker:
        overlay.checkbox_for("b").setChecked(True)

    assert blocker.args == ["b", True]


def test_toggling_does_not_close_the_dialog(qtbot):
    """The whole reason this is not `PickerOverlay`: a checklist reports a
    change and stays open."""
    overlay = ChecklistOverlay("Title")
    qtbot.addWidget(overlay)
    overlay.set_items([ChecklistItem("a", "A")])

    overlay.checkbox_for("a").setChecked(True)

    assert overlay.result() == 0


def test_a_changed_key_set_is_rebuilt(qtbot):
    overlay = ChecklistOverlay("Title")
    qtbot.addWidget(overlay)
    overlay.set_items([ChecklistItem("a", "A"), ChecklistItem("b", "B")])

    overlay.set_items([ChecklistItem("c", "C")])

    assert _rows(overlay) == ["c"]
    assert overlay.checkbox_for("a") is None
    assert overlay.checkbox_for("c") is not None


def test_an_unchanged_key_set_keeps_the_same_controls(qtbot):
    """Not an optimisation. A consumer with a cross-row rule calls `set_items`
    from *inside* a `toggled` emission, and rebuilding there would tear down
    the checkbox whose signal is still being delivered."""
    overlay = ChecklistOverlay("Title")
    qtbot.addWidget(overlay)
    overlay.set_items([ChecklistItem("a", "A"), ChecklistItem("b", "B")])
    before = overlay.checkbox_for("a")

    overlay.set_items(
        [ChecklistItem("a", "A", checked=True), ChecklistItem("b", "B", locked=True)]
    )

    assert overlay.checkbox_for("a") is before
    assert before.isChecked() is True
    assert overlay.checkbox_for("b").isEnabled() is False


def test_re_entrant_set_items_from_a_toggle_handler_survives(qtbot):
    """The order-execution dialog's exact shape: the toggle handler writes the
    screen's state, whose change signal calls `set_items` again. Written as a
    test because the in-place path exists for this and nothing else."""
    overlay = ChecklistOverlay("Title")
    qtbot.addWidget(overlay)
    overlay.set_items([ChecklistItem("0", "Bar close"), ChecklistItem("2", "Tick")])

    def enforce(key: str, checked: bool) -> None:
        overlay.set_items(
            [
                ChecklistItem("0", "Bar close", checked=not checked),
                ChecklistItem("2", "Tick", checked=checked),
            ]
        )

    overlay.toggled.connect(enforce)
    overlay.checkbox_for("2").setChecked(True)

    assert overlay.checkbox_for("0").isChecked() is False
    assert overlay.checkbox_for("2").isChecked() is True


def test_the_empty_state_says_so_rather_than_showing_a_blank_box(qtbot):
    overlay = ChecklistOverlay("Title", empty_text="Nothing is registered.")
    qtbot.addWidget(overlay)

    overlay.set_items([])

    assert overlay.items == ()
    assert overlay._empty_label.isVisibleTo(overlay) is True
    assert overlay._scroll.isVisibleTo(overlay) is False


def test_rows_replace_the_empty_state(qtbot):
    overlay = ChecklistOverlay("Title", empty_text="Nothing is registered.")
    qtbot.addWidget(overlay)
    overlay.set_items([])

    overlay.set_items([ChecklistItem("a", "A")])

    assert overlay._empty_label.isVisibleTo(overlay) is False
    assert overlay._scroll.isVisibleTo(overlay) is True


def test_an_unoffered_key_has_no_control(qtbot):
    overlay = ChecklistOverlay("Title")
    qtbot.addWidget(overlay)
    overlay.set_items([ChecklistItem("a", "A")])

    assert overlay.checkbox_for("nope") is None

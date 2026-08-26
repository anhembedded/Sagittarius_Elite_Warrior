"""Tests for `widgets.controls.styled_progress_bar.StyledProgressBar`."""

from __future__ import annotations

from PySide6.QtWidgets import QProgressBar
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import StyledProgressBar


def test_is_a_progress_bar_and_is_styled(qtbot):
    bar = StyledProgressBar()
    qtbot.addWidget(bar)

    assert isinstance(bar, QProgressBar)
    assert bar.styleSheet() != ""


def test_percentage_is_hidden_by_default(qtbot):
    """The consumer sets `setTextVisible(True)` on a bar it fixes to 10px
    tall with a 10px font — text that cannot fit. Nobody noticed because
    nothing in that app ever sets a value."""
    bar = StyledProgressBar()
    qtbot.addWidget(bar)

    assert bar.isTextVisible() is False


def test_indeterminate_uses_qts_own_busy_range(qtbot):
    bar = StyledProgressBar()
    qtbot.addWidget(bar)

    bar.set_indeterminate(True)

    assert bar.indeterminate is True
    assert (bar.minimum(), bar.maximum()) == (0, 0)


def test_leaving_indeterminate_restores_the_previous_range(qtbot):
    """The consumer makes `set_indeterminate(False)` a deliberate no-op to
    avoid clobbering a range set separately. Remembering the range removes
    the reason for that no-op."""
    bar = StyledProgressBar()
    qtbot.addWidget(bar)
    bar.setRange(0, 250)

    bar.set_indeterminate(True)
    bar.set_indeterminate(False)

    assert bar.indeterminate is False
    assert (bar.minimum(), bar.maximum()) == (0, 250)


def test_going_busy_twice_does_not_forget_the_real_range(qtbot):
    bar = StyledProgressBar()
    qtbot.addWidget(bar)
    bar.setRange(0, 250)

    bar.set_indeterminate(True)
    bar.set_indeterminate(True)
    bar.set_indeterminate(False)

    assert (bar.minimum(), bar.maximum()) == (0, 250)


def test_leaving_a_mode_it_was_never_in_is_harmless(qtbot):
    bar = StyledProgressBar()
    qtbot.addWidget(bar)
    bar.setRange(0, 40)

    bar.set_indeterminate(False)

    assert (bar.minimum(), bar.maximum()) == (0, 40)


def test_disabled_renders_differently(qtbot, fake_theme_bridge):
    bar = StyledProgressBar()
    qtbot.addWidget(bar)
    enabled_qss = bar.styleSheet()

    bar.setEnabled(False)

    assert bar.styleSheet() != enabled_qss
    assert "<muted>" in bar.styleSheet()

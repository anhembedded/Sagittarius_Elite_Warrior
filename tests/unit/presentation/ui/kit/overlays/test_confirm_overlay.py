"""Tests for `widgets.overlays.confirm_overlay.ConfirmOverlay`."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import ConfirmOverlay, Overlay
from Sagittarius_Elite_Warrior.src.presentation.ui.kit.style import StyleRole


def test_constructs_as_a_modal_overlay(qtbot):
    overlay = ConfirmOverlay("Delete everything?")
    qtbot.addWidget(overlay)

    assert isinstance(overlay, Overlay)
    assert isinstance(overlay, QDialog)
    assert overlay.isModal() is True


def test_buttons_exist_by_the_time_the_subclass_body_runs(qtbot):
    """The trap `Overlay._build_buttons`'s docstring warns about, and which
    the consuming app's `CapitalDialogWidget` fell into: both buttons are
    already real objects when `__init__` returns, so a subclass must not
    re-annotate them to `None` afterwards."""
    overlay = ConfirmOverlay("Title")
    qtbot.addWidget(overlay)

    assert overlay.confirm_button is not None
    assert overlay.cancel_button is not None


def test_button_labels_come_from_the_caller(qtbot):
    overlay = ConfirmOverlay(
        "XÁC NHẬN XÓA DỮ LIỆU",
        confirm_text="Xác nhận Xóa",
        cancel_text="Hủy bỏ",
    )
    qtbot.addWidget(overlay)

    assert overlay.confirm_button.text() == "Xác nhận Xóa"
    assert overlay.cancel_button.text() == "Hủy bỏ"


def test_confirm_accepts_and_cancel_rejects(qtbot):
    accepted = ConfirmOverlay("Title")
    qtbot.addWidget(accepted)
    with qtbot.waitSignal(accepted.accepted, timeout=1000):
        accepted.confirm_button.click()

    rejected = ConfirmOverlay("Title")
    qtbot.addWidget(rejected)
    with qtbot.waitSignal(rejected.rejected, timeout=1000):
        rejected.cancel_button.click()


def test_danger_flag_selects_the_destructive_role(qtbot, fake_theme_bridge):
    # `fake_theme_bridge`, not the real singleton: this asserts two roles
    # render *differently*, and `get_theme_bridge()` is process-wide
    # first-caller-wins. In the full session `test_overlay_host.py`'s
    # all-#000000 placeholder wins that race, which collapses every token to
    # the same value and makes the comparison below pass or fail on
    # collection order. The `widgets/` conftest documents this exact trap and
    # supplies this fixture for it.
    danger = ConfirmOverlay("Purge vault", danger=True)
    qtbot.addWidget(danger)
    benign = ConfirmOverlay("Save changes")
    qtbot.addWidget(benign)

    assert danger.danger is True
    assert danger.confirm_button._role is StyleRole.DANGER_BUTTON
    assert benign.danger is False
    assert benign.confirm_button._role is StyleRole.PRIMARY_BUTTON
    # Not merely a different flag — a different rendering.
    assert danger.confirm_button.styleSheet() != benign.confirm_button.styleSheet()


def test_cancel_is_always_the_secondary_role(qtbot):
    overlay = ConfirmOverlay("Purge vault", danger=True)
    qtbot.addWidget(overlay)

    assert overlay.cancel_button._role is StyleRole.SECONDARY_BUTTON


def test_message_is_shown_only_when_given(qtbot):
    without = ConfirmOverlay("Title")
    qtbot.addWidget(without)
    with_message = ConfirmOverlay("Title", message="This cannot be undone.")
    qtbot.addWidget(with_message)

    assert without._message_label.isVisibleTo(without) is False
    assert with_message.message == "This cannot be undone."
    assert with_message._message_label.isVisibleTo(with_message) is True


def test_message_setter_toggles_visibility(qtbot):
    overlay = ConfirmOverlay("Title")
    qtbot.addWidget(overlay)

    overlay.message = "Now there is something to read"
    assert overlay._message_label.isVisibleTo(overlay) is True

    overlay.message = ""
    assert overlay._message_label.isVisibleTo(overlay) is False


def test_subtitle_still_works_through_the_base(qtbot):
    overlay = ConfirmOverlay("Title", "Subtitle text", message="Body")
    qtbot.addWidget(overlay)

    assert overlay.title == "Title"
    assert overlay.subtitle == "Subtitle text"
    assert overlay.message == "Body"

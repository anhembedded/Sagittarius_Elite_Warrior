"""Render and interaction tests for `ProgressBanner.qml`."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest


def test_status_text_and_rounded_percent_are_shown(load_qml, qml_item):
    quick, root = load_qml("ProgressBanner.qml")
    root.setProperty("statusText", "Đang chạy backtest…")
    root.setProperty("percent", 61.7)

    status = qml_item(root, "progressBannerStatusText")
    percent = qml_item(root, "progressBannerPercentText")

    assert status.property("text") == "Đang chạy backtest…"
    assert percent.property("text") == "62%"
    quick.close()
    quick.deleteLater()


def test_the_fill_width_tracks_percent(load_qml, qml_item):
    quick, root = load_qml("ProgressBanner.qml")
    track = qml_item(root, "progressBannerTrack")
    fill = qml_item(root, "progressBannerFill")

    root.setProperty("percent", 0)
    # Margin is generous, not the 150ms animation's own duration plus a
    # sliver — a too-tight margin here is exactly the kind of timing flake
    # that reproduces under full-parallel xdist load and passes standalone
    # (see tests/unit/.../test_history_pagination_controller.py's fix,
    # 2026-08-30, same lesson).
    QTest.qWait(500)  # let the width Behavior's animation settle
    empty_width = fill.property("width")
    root.setProperty("percent", 100)
    QTest.qWait(500)
    full_width = fill.property("width")
    quick.close()
    quick.deleteLater()

    assert empty_width == 0
    assert full_width == track.property("width")


def test_indeterminate_mode_hides_the_percent_text_and_fill(load_qml, qml_item):
    quick, root = load_qml("ProgressBanner.qml")
    root.setProperty("indeterminate", True)

    percent = qml_item(root, "progressBannerPercentText")
    fill = qml_item(root, "progressBannerFill")
    sweep = qml_item(root, "progressBannerIndeterminateSweep")

    assert percent.property("visible") is False
    assert fill.property("visible") is False
    assert sweep.property("visible") is True
    quick.close()
    quick.deleteLater()


def test_clicking_cancel_emits_the_signal(load_qml, qml_item):
    quick, root = load_qml("ProgressBanner.qml")
    button = qml_item(root, "progressBannerCancelButton")
    cancels: list[None] = []
    root.cancelRequested.connect(lambda: cancels.append(None))

    centre = button.mapToScene(button.boundingRect().center())
    QTest.mouseClick(
        quick, Qt.MouseButton.LeftButton, pos=QPoint(int(centre.x()), int(centre.y()))
    )

    assert cancels == [None]
    quick.close()
    quick.deleteLater()


def test_cancelling_disables_the_button_and_relabels_it(load_qml, qml_item):
    quick, root = load_qml("ProgressBanner.qml")
    root.setProperty("cancelling", True)
    button = qml_item(root, "progressBannerCancelButton")
    label = qml_item(button, "buttonLabel")

    assert button.property("enabled") is False
    assert label.property("text") == "Đang hủy..."
    quick.close()
    quick.deleteLater()

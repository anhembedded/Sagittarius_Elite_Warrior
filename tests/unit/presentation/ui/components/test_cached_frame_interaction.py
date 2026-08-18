import math

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.cached_frame_interaction import (
    _BACKGROUND_COLOR,
    shifted_x_range,
    zoomed_x_range,
)


def test_shifted_x_range_translates_data_opposite_to_drag_direction():
    shifted = shifted_x_range((100.0, 200.0), pixel_delta=160.0, viewport_width=1600.0)

    assert shifted == (90.0, 190.0)


def test_zoomed_x_range_preserves_the_data_point_under_the_cursor():
    zoomed = zoomed_x_range(
        (100.0, 200.0),
        anchor_ratio=0.25,
        preview_scale=2.0,
    )

    assert zoomed == (112.5, 162.5)


def test_cached_pan_previews_pixels_then_commits_exact_data_range(qapp):
    card = ChartCard("BTCUSDT", cached_interaction=True)
    card.resize(1200, 700)
    card.show()
    candles = [(float(index * 60), 100.0, 102.0, 98.0, 101.0) for index in range(240)]
    card.render_historical_data(candles)
    card.plot_layout.main_plot.setXRange(3600.0, 9600.0, padding=0)
    qapp.processEvents()
    controller = card.cached_interaction
    assert controller is not None
    start_range = tuple(card.plot_layout.main_plot.vb.viewRange()[0])
    view_rect = card.plot_layout.main_plot.vb.sceneBoundingRect()
    viewport_start = QPointF(card.plot_layout.widget.mapFromScene(view_rect.center()))
    viewport_end = viewport_start + QPointF(view_rect.width() * 0.1, 0.0)

    assert controller.begin_pan(viewport_start) is True
    controller.update_pan(viewport_end)

    assert controller.is_preview_active is True
    assert tuple(card.plot_layout.main_plot.vb.viewRange()[0]) == start_range

    controller.commit_pan(viewport_end)
    qapp.processEvents()

    expected = shifted_x_range(
        start_range,
        pixel_delta=view_rect.width() * 0.1,
        viewport_width=view_rect.width(),
    )
    actual = card.plot_layout.main_plot.vb.viewRange()[0]
    assert math.isclose(actual[0], expected[0], abs_tol=1e-6)
    assert math.isclose(actual[1], expected[1], abs_tol=1e-6)
    assert controller.is_preview_active is False
    card.cleanup()


def test_cached_zoom_previews_pixels_then_commits_exact_anchored_range(qapp):
    card = ChartCard("BTCUSDT", cached_interaction=True)
    card.resize(1200, 700)
    card.show()
    candles = [(float(index * 60), 100.0, 102.0, 98.0, 101.0) for index in range(240)]
    card.render_historical_data(candles)
    card.plot_layout.main_plot.setXRange(3600.0, 9600.0, padding=0)
    qapp.processEvents()
    controller = card.cached_interaction
    assert controller is not None
    start_range = tuple(card.plot_layout.main_plot.vb.viewRange()[0])
    view_rect = card.plot_layout.main_plot.vb.sceneBoundingRect()
    anchor = QPointF(
        card.plot_layout.widget.mapFromScene(
            QPointF(
                view_rect.left() + view_rect.width() * 0.25,
                view_rect.center().y(),
            )
        )
    )
    anchor_scene = card.plot_layout.widget.mapToScene(anchor.toPoint())
    actual_anchor_ratio = (anchor_scene.x() - view_rect.left()) / view_rect.width()

    assert controller.begin_zoom(anchor) is True
    controller.update_zoom(preview_scale=2.0)

    assert controller.is_preview_active is True
    assert tuple(card.plot_layout.main_plot.vb.viewRange()[0]) == start_range

    controller.commit_zoom()
    qapp.processEvents()

    expected = zoomed_x_range(
        start_range,
        anchor_ratio=actual_anchor_ratio,
        preview_scale=2.0,
    )
    actual = card.plot_layout.main_plot.vb.viewRange()[0]
    assert math.isclose(actual[0], expected[0], abs_tol=1e-6)
    assert math.isclose(actual[1], expected[1], abs_tol=1e-6)
    assert controller.is_preview_active is False
    card.cleanup()


def test_real_mouse_drag_uses_cached_preview_and_commits_on_release(qapp):
    card = ChartCard("BTCUSDT", cached_interaction=True)
    card.resize(1200, 700)
    card.show()
    card.render_historical_data(
        [(float(index * 60), 100.0, 102.0, 98.0, 101.0) for index in range(240)]
    )
    card.plot_layout.main_plot.setXRange(3600.0, 9600.0, padding=0)
    qapp.processEvents()
    controller = card.cached_interaction
    assert controller is not None
    viewport = card.plot_layout.widget.viewport()
    view_rect = card.plot_layout.main_plot.vb.sceneBoundingRect()
    start = card.plot_layout.widget.mapFromScene(view_rect.center())
    end = start + QPoint(100, 0)
    initial_range = tuple(card.plot_layout.main_plot.vb.viewRange()[0])
    card.range_updates.flush_pending()
    initial_range_applies = card.range_updates.applied_count

    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    for offset in range(10, 101, 10):
        QTest.mouseMove(viewport, start + QPoint(offset, 0))
    qapp.processEvents()

    assert controller.is_preview_active is True
    assert tuple(card.plot_layout.main_plot.vb.viewRange()[0]) == initial_range
    assert card.range_updates.applied_count == initial_range_applies

    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
    card.range_updates.flush_pending()

    assert controller.is_preview_active is False
    assert tuple(card.plot_layout.main_plot.vb.viewRange()[0]) != initial_range
    assert card.range_updates.applied_count == initial_range_applies + 1
    card.cleanup()


def test_viewport_resize_mid_pan_preview_commits_instead_of_stretching_stale_frame(
    qapp,
):
    """Regression test for BUG-009.

    `_CachedFrameOverlay.begin()` grabs a snapshot pixmap sized to the
    viewport at the moment a drag starts, and the eventFilter's Resize
    branch used to only call `self._overlay.setGeometry(...)` — resizing the
    *overlay widget* to track the live viewport but never touching the
    *cached pixmap*, which stayed the old, smaller size. `paintEvent` always
    draws that pixmap at its native size from (0, 0) and fills the rest of
    the overlay with `_BACKGROUND_COLOR` first, so a resize mid-drag left a
    small patch of the old frame sitting in the corner of an otherwise blank
    overlay — exactly the user-reported "sao move chart mà nó lại move cái
    widget chart... sau khi nhả chuột thì nó trở về chỗ cũ" symptom: most of
    the chart area goes blank/black around a small remaining candle patch,
    then snaps back correct on release.
    """
    card = ChartCard("BTCUSDT", cached_interaction=True)
    card.resize(1200, 700)
    card.show()
    candles = [(float(index * 600), 100.0, 102.0, 98.0, 101.0) for index in range(40)]
    card.render_historical_data(candles)
    card.plot_layout.main_plot.setXRange(0.0, 23400.0, padding=0)
    qapp.processEvents()

    controller = card.cached_interaction
    assert controller is not None
    view_rect = card.plot_layout.main_plot.vb.sceneBoundingRect()
    start = QPointF(card.plot_layout.widget.mapFromScene(view_rect.center()))

    assert controller.begin_pan(start) is True
    controller.update_pan(start + QPointF(30.0, 0.0))
    overlay = controller.preview_surface
    stale_frame_size = overlay._frame.size()
    assert controller.is_preview_active is True

    # Something outside this interaction resizes the chart mid-drag — a
    # window resize, a splitter move, or a dynamic layout change (e.g. a
    # banner appearing) all fire the exact same viewport Resize event.
    card.resize(1200, 1400)
    qapp.processEvents()
    qapp.processEvents()

    # The overlay geometry now exceeds the stale cached pixmap it grabbed
    # at drag-start — the precondition for the visual defect.
    assert overlay.geometry().height() > stale_frame_size.height()

    # A resize mid-preview must commit immediately (hiding the overlay)
    # rather than leaving a stale, undersized pixmap stretched across a
    # newly-enlarged overlay.
    assert controller.is_preview_active is False
    assert overlay.isVisible() is False

    # With the overlay hidden, sampling the region that used to sit below
    # the stale frame's old bottom edge must show the real, live chart
    # widget underneath — never the overlay's own sentinel fill color,
    # which is what a leftover stale overlay would paint there.
    below_stale_frame = (
        card.grab()
        .toImage()
        .pixelColor(card.width() // 2, stale_frame_size.height() + 200)
    )
    assert QColor(below_stale_frame) != _BACKGROUND_COLOR

    card.cleanup()


def test_real_wheel_event_uses_cached_preview_and_commits_after_burst(qapp):
    card = ChartCard("BTCUSDT", cached_interaction=True)
    card.resize(1200, 700)
    card.show()
    card.render_historical_data(
        [(float(index * 60), 100.0, 102.0, 98.0, 101.0) for index in range(240)]
    )
    card.plot_layout.main_plot.setXRange(3600.0, 9600.0, padding=0)
    qapp.processEvents()
    controller = card.cached_interaction
    assert controller is not None
    viewport = card.plot_layout.widget.viewport()
    view_rect = card.plot_layout.main_plot.vb.sceneBoundingRect()
    position = QPointF(card.plot_layout.widget.mapFromScene(view_rect.center()))
    global_position = QPointF(viewport.mapToGlobal(position.toPoint()))
    initial_range = tuple(card.plot_layout.main_plot.vb.viewRange()[0])
    card.range_updates.flush_pending()
    initial_range_applies = card.range_updates.applied_count
    wheel_event = QWheelEvent(
        position,
        global_position,
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    QApplication.sendEvent(viewport, wheel_event)
    qapp.processEvents()

    assert wheel_event.isAccepted() is True
    assert controller.is_preview_active is True
    assert tuple(card.plot_layout.main_plot.vb.viewRange()[0]) == initial_range
    assert card.range_updates.applied_count == initial_range_applies

    controller.commit_zoom()
    card.range_updates.flush_pending()

    assert controller.is_preview_active is False
    assert tuple(card.plot_layout.main_plot.vb.viewRange()[0]) != initial_range
    assert card.range_updates.applied_count == initial_range_applies + 1
    card.cleanup()

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

#: Short enough to stay inside the cached frame on every card size used here,
#: so a test of the pure preview transform never trips the mid-drag re-render.
_SHORT_PAN_PIXELS = 40.0


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
    # Kept below the re-anchor threshold on purpose: this test covers the pure
    # cached-pixmap regime, where the real plot must not move until commit.
    # Re-anchoring past that threshold is covered by its own tests below.
    viewport_end = viewport_start + QPointF(_SHORT_PAN_PIXELS, 0.0)

    assert controller.begin_pan(viewport_start) is True
    controller.update_pan(viewport_end)

    assert controller.is_preview_active is True
    assert tuple(card.plot_layout.main_plot.vb.viewRange()[0]) == start_range

    controller.commit_pan(viewport_end)
    qapp.processEvents()

    expected = shifted_x_range(
        start_range,
        pixel_delta=_SHORT_PAN_PIXELS,
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
    # Below the re-anchor threshold — see _SHORT_PAN_PIXELS.
    end = start + QPoint(int(_SHORT_PAN_PIXELS), 0)
    initial_range = tuple(card.plot_layout.main_plot.vb.viewRange()[0])
    card.range_updates.flush_pending()
    initial_range_applies = card.range_updates.applied_count

    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    for offset in range(10, int(_SHORT_PAN_PIXELS) + 1, 10):
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
    """Regression test for a secondary defect found while investigating BUG-009.

    This is NOT the defect BUG-009 actually reported — see
    `test_pan_preview_moves_only_the_data_region_not_the_axes` below for
    that one. It is a separate stale-pixmap bug found in the same code while
    investigating, kept because it is real and reachable on its own.

    `_CachedFrameOverlay.begin()` grabs a snapshot pixmap sized to the
    viewport at the moment a drag starts, and the eventFilter's Resize
    branch used to only call `self._overlay.setGeometry(...)` — resizing the
    *overlay widget* to track the live viewport but never touching the
    *cached pixmap*, which stayed the old, smaller size. `paintEvent` draws
    that pixmap at its native size from (0, 0) over a `_BACKGROUND_COLOR`
    fill, so a resize mid-drag left a small patch of the old frame sitting
    in the corner of an otherwise blank overlay.
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


def _axis_strip_signature(image, strip_width: int) -> list[tuple[int, ...]]:
    """Column-by-column pixel signature of the Y-axis strip left of the plot."""
    columns: list[tuple[int, ...]] = []
    for x in range(strip_width):
        columns.append(
            tuple(image.pixelColor(x, y).rgb() for y in range(0, image.height(), 5))
        )
    return columns


def test_pan_preview_moves_only_the_data_region_not_the_axes(qapp):
    """Regression test for the defect BUG-009 actually reported.

    `_CachedFrameOverlay.begin()` caches `self._viewport.grab()` — a snapshot
    of the ENTIRE viewport, which includes the price axis, its tick labels,
    the time axis and every subplot's axis, not just the candle area.
    `paintEvent` then applied the pan/zoom transform to that whole pixmap, so
    dragging translated the axes and labels sideways along with the candles
    and revealed bare `_BACKGROUND_COLOR` where the frame no longer covered.
    To the user this reads as the whole chart widget sliding inside its own
    frame and snapping back on release, rather than candles panning within a
    stationary axis frame: "miễn chọn trong khung lưới là sẽ move cả cái
    graph".

    The axis strip is chart chrome, not panned data — it must be pixel-
    identical before and during a drag, while the data region must still
    visibly change (otherwise the preview would be "fixed" by doing nothing).
    """
    card = ChartCard("BTCUSDT", cached_interaction=True)
    card.resize(1200, 700)
    card.show()
    candles = [
        (float(index * 60), 100.0 + (index % 7), 102.0 + (index % 5), 98.0, 101.0)
        for index in range(240)
    ]
    card.render_historical_data(candles)
    card.plot_layout.main_plot.setXRange(3600.0, 9600.0, padding=0)
    qapp.processEvents()

    controller = card.cached_interaction
    assert controller is not None
    canvas = card.plot_layout.widget
    viewport = canvas.viewport()
    view_rect = card.plot_layout.main_plot.vb.sceneBoundingRect()
    # Everything left of the plot's data area is the price axis and its tick
    # labels — chrome that a pan must never move.
    axis_strip_width = canvas.mapFromScene(view_rect.topLeft()).x()
    assert axis_strip_width > 0

    before_image = viewport.grab().toImage()
    before_axis = _axis_strip_signature(before_image, axis_strip_width)

    # Deliberately shorter than _PAN_REANCHOR_VIEWPORT_RATIO of the plot
    # width, so this stays a test of the pure cached-pixmap transform and
    # never trips the mid-drag re-render (covered separately below).
    start = QPointF(canvas.mapFromScene(view_rect.center()))
    assert controller.begin_pan(start) is True
    controller.update_pan(start + QPointF(100.0, 0.0))
    qapp.processEvents()

    during_image = viewport.grab().toImage()
    during_axis = _axis_strip_signature(during_image, axis_strip_width)

    assert controller.is_preview_active is True
    assert during_axis == before_axis, (
        "the price axis moved with the drag — the pan transform is being "
        "applied to the whole cached viewport frame instead of only the "
        "plot's data region"
    )

    # The preview must still actually preview: the data region has to change,
    # or this test would also pass against a no-op overlay.
    data_x = int(canvas.mapFromScene(view_rect.center()).x())
    data_column_before = tuple(
        before_image.pixelColor(data_x, y).rgb()
        for y in range(0, before_image.height(), 5)
    )
    data_column_during = tuple(
        during_image.pixelColor(data_x, y).rgb()
        for y in range(0, during_image.height(), 5)
    )
    assert data_column_during != data_column_before

    # The time axis is the one piece of chrome that MUST follow the drag:
    # leaving it pinned while the candles slide would put every timestamp
    # under the wrong candle for the duration of the gesture.
    time_axis = card.plot_layout.plots[-1].getAxis("bottom")
    time_axis_rect = canvas.mapFromScene(time_axis.sceneBoundingRect()).boundingRect()
    time_axis_y = time_axis_rect.center().y()
    time_axis_before = tuple(
        before_image.pixelColor(x, time_axis_y).rgb()
        for x in range(time_axis_rect.left(), time_axis_rect.right(), 3)
    )
    time_axis_during = tuple(
        during_image.pixelColor(x, time_axis_y).rgb()
        for x in range(time_axis_rect.left(), time_axis_rect.right(), 3)
    )
    assert time_axis_during != time_axis_before

    controller.commit_pan(start + QPointF(100.0, 0.0))
    card.cleanup()


def test_long_drag_does_not_expose_a_large_blank_band(qapp):
    """Regression test for the blank area left behind by a long drag.

    The cached frame only holds the pixels that were on screen when the drag
    started, so translating it far enough exposes a band it has no content
    for. Fixing the axis-sliding half of BUG-009 stopped the chrome from
    moving but left this band growing without bound: the user reported it
    again, with most of the plot blank around the surviving candles.

    `_reanchor_pan` caps it by re-rendering the real plot and re-grabbing
    once a drag passes `_PAN_REANCHOR_VIEWPORT_RATIO` of the plot width.
    """
    card = ChartCard("BTCUSDT", cached_interaction=True)
    card.resize(1200, 700)
    card.show()
    candles = [
        (float(index * 60), 100.0 + (index % 7), 102.0 + (index % 5), 98.0, 101.0)
        for index in range(600)
    ]
    card.render_historical_data(candles)
    card.plot_layout.main_plot.setXRange(3600.0, 9600.0, padding=0)
    qapp.processEvents()

    controller = card.cached_interaction
    assert controller is not None
    canvas = card.plot_layout.widget
    viewport = canvas.viewport()
    view_rect = card.plot_layout.main_plot.vb.sceneBoundingRect()
    region = canvas.mapFromScene(view_rect).boundingRect()

    start = QPointF(canvas.mapFromScene(view_rect.center()))
    assert controller.begin_pan(start) is True
    # Drag most of the way across the plot — far past anything a single
    # cached frame could cover.
    for offset in range(40, int(region.width() * 0.75), 40):
        controller.update_pan(start + QPointF(float(offset), 0.0))
    qapp.processEvents()

    image = viewport.grab().toImage()
    # Judge a whole column, not a single row: the preview's crosshair paints
    # one row right across the blank band, so a single-row sample measures
    # the crosshair instead of the background and reports no blank at all.
    rows = range(region.top() + 4, region.bottom() - 4, 8)
    blank_columns = 0
    total_columns = 0
    for x in range(region.left() + 2, region.right() - 2, 4):
        total_columns += 1
        background_rows = sum(
            1 for y in rows if image.pixelColor(x, y) == _BACKGROUND_COLOR
        )
        if background_rows >= len(list(rows)) * 0.9:
            blank_columns += 1
    blank_fraction = blank_columns / total_columns

    assert blank_fraction <= 0.25, (
        f"{blank_fraction:.0%} of the plot width is bare overlay background "
        "mid-drag — the cached frame is being translated far beyond the "
        "pixels it actually holds"
    )

    controller.commit_pan()
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


def test_reanchoring_mid_drag_lands_on_the_same_range_as_one_continuous_pan(qapp):
    """A long drag must not drift just because it was re-anchored on the way.

    `_reanchor_pan` resets `_initial_range` and `_start_position` each time it
    fires, so a single drag past the threshold is committed as a chain of
    shorter shifts rather than one. Those must compose exactly: if they did
    not, panning slowly (many re-anchors) would land somewhere different from
    panning quickly (few), and the chart would creep away from the candle the
    user was dragging to.
    """
    total_pan_pixels = 600.0

    def pan_and_read_final_range(step_pixels: float) -> tuple[float, float]:
        card = ChartCard("BTCUSDT", cached_interaction=True)
        card.resize(1200, 700)
        card.show()
        card.render_historical_data(
            [
                (float(index * 60), 100.0 + (index % 7), 102.0, 98.0, 101.0)
                for index in range(600)
            ]
        )
        card.plot_layout.main_plot.setXRange(9000.0, 18000.0, padding=0)
        qapp.processEvents()
        controller = card.cached_interaction
        assert controller is not None
        view_rect = card.plot_layout.main_plot.vb.sceneBoundingRect()
        start = QPointF(card.plot_layout.widget.mapFromScene(view_rect.center()))

        assert controller.begin_pan(start) is True
        offset = step_pixels
        while offset < total_pan_pixels:
            controller.update_pan(start + QPointF(offset, 0.0))
            offset += step_pixels
        controller.update_pan(start + QPointF(total_pan_pixels, 0.0))
        controller.commit_pan(start + QPointF(total_pan_pixels, 0.0))
        qapp.processEvents()
        final_range = tuple(card.plot_layout.main_plot.vb.viewRange()[0])
        card.cleanup()
        return final_range

    # Same gesture, different event granularity: fine steps re-anchor far more
    # often than coarse ones.
    fine = pan_and_read_final_range(10.0)
    coarse = pan_and_read_final_range(50.0)

    assert math.isclose(fine[0], coarse[0], rel_tol=1e-9)
    assert math.isclose(fine[1], coarse[1], rel_tol=1e-9)

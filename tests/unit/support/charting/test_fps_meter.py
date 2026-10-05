from PySide6.QtCore import QRect
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QApplication, QWidget
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.fps_meter import (
    ChartFpsMeter,
    FrameRateSampler,
)


def test_frame_rate_sampler_reports_actual_paint_rate_and_resets() -> None:
    sampler = FrameRateSampler()
    for _ in range(30):
        sampler.record_frame()

    assert sampler.sample(500) == 60.0
    assert sampler.sample(500) == 0.0


def test_frame_rate_sampler_rejects_non_positive_elapsed_time() -> None:
    sampler = FrameRateSampler()
    sampler.record_frame()

    assert sampler.sample(0) == 0.0


def test_the_meter_follows_a_replaced_viewport(qapp) -> None:
    """`ChartCard` swaps a failed GL viewport for a CPU one; the meter must
    count paints of the new viewport and stop watching the old one."""
    old_viewport, new_viewport = QWidget(), QWidget()
    meter = ChartFpsMeter(old_viewport)
    meter.set_enabled(True)

    meter.release_viewport()
    meter.watch_viewport(new_viewport)
    QApplication.sendEvent(old_viewport, QPaintEvent(QRect()))
    QApplication.sendEvent(new_viewport, QPaintEvent(QRect()))
    QApplication.sendEvent(new_viewport, QPaintEvent(QRect()))

    assert meter._sampler.sample(1000) == 2.0
    meter.dispose()

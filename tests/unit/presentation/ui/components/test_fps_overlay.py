from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.fps_overlay import (
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

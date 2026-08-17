from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.range_update_scheduler import (
    RangeUpdateScheduler,
)


def test_range_update_scheduler_coalesces_burst_to_the_final_range(qapp) -> None:
    applied: list[tuple[float, float]] = []
    scheduler = RangeUpdateScheduler(
        lambda min_x, max_x: applied.append((min_x, max_x))
    )

    scheduler.schedule(100.0, 200.0)
    scheduler.schedule(110.0, 210.0)
    scheduler.schedule(120.0, 220.0)
    scheduler.flush_pending()

    assert applied == [(120.0, 220.0)]


def test_range_update_scheduler_dispose_drops_pending_work(qapp) -> None:
    applied: list[tuple[float, float]] = []
    scheduler = RangeUpdateScheduler(
        lambda min_x, max_x: applied.append((min_x, max_x))
    )
    scheduler.schedule(100.0, 200.0)

    scheduler.dispose()
    scheduler.flush_pending()

    assert applied == []

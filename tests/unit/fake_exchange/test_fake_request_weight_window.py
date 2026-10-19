"""`BUG-232` - the fake exchange's weight window is a calendar minute of its clock, and a test can hold it.

@details Binance's used-weight window resets at a minute edge, and so does the fake's `WeightMeter`
(it buckets by `int(clock() // 60)`). With the wall clock that edge falls wherever the runner happens
to be, so a test that says "these requests are inside one minute" failed at random when they were
not. `use_clock` lets such a test hold the minute still.
"""

from __future__ import annotations

from tests.sanity.fake_exchange.request_weight import WeightMeter

_PATH = "/api/v3/account"


def test_the_weight_used_in_a_minute_resets_at_the_minute_edge() -> None:
    now = [59.0]
    meter = WeightMeter(clock=lambda: now[0])

    first = meter.charge("GET", _PATH, {})
    now[0] = 61.0
    second = meter.charge("GET", _PATH, {})

    assert second == first, "the second request opened a new minute"


def test_a_held_clock_keeps_every_request_in_one_minute() -> None:
    now = [59.0]
    meter = WeightMeter(clock=lambda: now[0])
    first = meter.charge("GET", _PATH, {})

    meter.use_clock(lambda: 0.0)
    held = [meter.charge("GET", _PATH, {}) for _ in range(3)]

    assert held == [first + 1, first + 2, first + 3], (
        "one minute: the weight only adds up"
    )

"""`BOT-226` — between the 70 % line and the hard line the venue serves the reads that guard exits.

`BUG-247`: two wide ladders closed the weight gate at 70 % and every read failed, so a bot's stop
loss and take profit were not judged for the rest of the minute. The gate now closes to routine
requests at 70 % and to every request at 90 %; a read made inside `prioritised(EXIT_GUARD)` (its
position, the mark price, its open protective stops) is sent in between.

The session is the real `ResilientSession` over a recording client, the gate and the policy are
the real ones, and the weight is told the way production tells it: after an answer.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limited_api_exception import (
    RateLimitedApiException,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.resilient_session import (
    ResilientSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
    current_priority,
    prioritised,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.exchange_answers import (
    rate_limited,
)

_LIMIT = 2400
_SOFT_LINE = 1680  # 70 %
_HARD_LINE = 2160  # 90 %
_MINUTE_START = 6000.0


class _Exchange:
    """The few futures methods the three guarding reads and a ladder order use."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.used_weight = 0
        self.failure: Exception | None = None
        self.response = SimpleNamespace(headers={})

    def _answer(self, name: str) -> str:
        self.sent.append(name)
        if self.failure is not None:
            raise self.failure
        self.response.headers = {"x-mbx-used-weight-1m": str(self.used_weight)}
        return name

    def futures_position_information(self, **_: object) -> str:
        return self._answer("positions")

    def futures_mark_price(self, **_: object) -> str:
        return self._answer("mark")

    def futures_get_open_algo_orders(self, **_: object) -> str:
        return self._answer("stops")

    def futures_get_open_orders(self, **_: object) -> str:
        return self._answer("ladder_reads")

    def futures_create_order(self, **_: object) -> str:
        return self._answer("place")


class _Venue:
    def __init__(self) -> None:
        self.mono = [0.0]
        self.wall = [_MINUTE_START + 20.0]
        self.exchange = _Exchange()
        self.gate = RateLimitGate(lambda: self.mono[0])
        self.policy = ExchangeCallPolicy(
            self.gate,
            sleep=lambda _: None,
            wall_seconds=lambda: self.wall[0],
            weight_limit=_LIMIT,
        )
        self.session = ResilientSession(self.exchange, self.policy)

    def at_weight(self, used: int) -> None:
        """The exchange has reported `used` weight on an answer (`note_used_weight_header`)."""
        self.policy.note_used_weight_header(str(used))

    def advance(self, seconds: float) -> None:
        self.mono[0] += seconds
        self.wall[0] += seconds

    def guard_reads(self) -> list[str]:
        with prioritised(RequestPriority.EXIT_GUARD):
            return [
                str(self.session.futures_position_information()),
                str(self.session.futures_mark_price(symbol="BTCUSDT")),
                str(self.session.futures_get_open_algo_orders(symbol="BTCUSDT")),
            ]


def test_the_reads_that_guard_exits_pass_in_the_reserve() -> None:
    venue = _Venue()
    venue.at_weight(_SOFT_LINE)

    answers = venue.guard_reads()

    assert answers == ["positions", "mark", "stops"]
    assert venue.exchange.sent == ["positions", "mark", "stops"]


def test_routine_traffic_waits_at_the_70_percent_line_as_before() -> None:
    venue = _Venue()
    venue.at_weight(_SOFT_LINE)

    with pytest.raises(RateLimitedApiException) as refused:
        venue.session.futures_get_open_orders(symbol="BTCUSDT")
    with pytest.raises(RateLimitedApiException):
        venue.session.futures_create_order(symbol="BTCUSDT")

    assert venue.exchange.sent == [], "a refused request is never sent"
    assert not refused.value.banned
    assert "reserve" in str(refused.value), (
        "the refusal says why, not 'the exchange asked'"
    )


def test_a_routine_read_inside_a_guarding_scope_is_not_a_guard_after_it_ends() -> None:
    venue = _Venue()
    venue.at_weight(_SOFT_LINE)
    venue.guard_reads()

    assert current_priority() is RequestPriority.ROUTINE
    with pytest.raises(RateLimitedApiException):
        venue.session.futures_get_open_orders(symbol="BTCUSDT")


def test_nothing_is_sent_at_the_hard_line_not_even_a_guard() -> None:
    venue = _Venue()
    venue.at_weight(_HARD_LINE - 1)
    assert venue.guard_reads() == ["positions", "mark", "stops"], (
        "just under: a reserve"
    )
    venue.exchange.sent.clear()

    venue.at_weight(_HARD_LINE)
    with pytest.raises(RateLimitedApiException):
        venue.guard_reads()

    assert venue.exchange.sent == []


def test_an_answer_that_pushes_the_weight_past_the_hard_line_closes_the_next_guard() -> (
    None
):
    venue = _Venue()
    venue.at_weight(_SOFT_LINE)
    venue.exchange.used_weight = _HARD_LINE + 40
    with prioritised(RequestPriority.EXIT_GUARD):
        assert venue.session.futures_position_information() == "positions"
        with pytest.raises(RateLimitedApiException):
            venue.session.futures_mark_price(symbol="BTCUSDT")


def test_a_rate_limit_answer_closes_the_guards_too() -> None:
    venue = _Venue()
    venue.at_weight(_SOFT_LINE)
    venue.exchange.failure = rate_limited(429, retry_after="20")

    with prioritised(RequestPriority.EXIT_GUARD):
        with pytest.raises(RateLimitedApiException):
            venue.session.futures_position_information()
        venue.exchange.sent.clear()
        with pytest.raises(RateLimitedApiException):
            venue.session.futures_mark_price(symbol="BTCUSDT")

    assert venue.exchange.sent == [], "the exchange asked for a pause: nobody sends"


def test_everything_resumes_when_the_minute_turns() -> None:
    venue = _Venue()
    venue.at_weight(_SOFT_LINE)
    with pytest.raises(RateLimitedApiException):
        venue.session.futures_get_open_orders(symbol="BTCUSDT")

    venue.advance(
        42.0
    )  # 20 s into the minute + 42: the reserve's pause ran to the minute's end +1

    assert venue.session.futures_get_open_orders(symbol="BTCUSDT") == "ladder_reads"


def test_the_reserve_is_told_once_and_the_end_of_it_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    venue = _Venue()
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")
    venue.at_weight(_SOFT_LINE)
    venue.at_weight(_SOFT_LINE + 30)
    venue.guard_reads()
    venue.advance(42.0)
    venue.session.futures_get_open_orders(symbol="BTCUSDT")
    venue.session.futures_get_open_orders(symbol="BTCUSDT")

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert len(warnings) == 1
    assert "routine requests are not sent" in warnings[0]
    assert "reads that guard exits still pass" in warnings[0]
    assert "[rate-limit-reserve]" in warnings[0]
    assert len(infos) == 1 and "rate-limit-end" in infos[0]


def test_reaching_the_hard_line_after_the_reserve_is_told_again(
    caplog: pytest.LogCaptureFixture,
) -> None:
    venue = _Venue()
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")
    venue.at_weight(_SOFT_LINE)

    venue.at_weight(_HARD_LINE)

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2, "the reserve, then the pause that holds everything"
    assert "[rate-limit-reserve]" in warnings[0]
    assert "no request is sent" in warnings[1] and "[rate-limit-soft]" in warnings[1]


def test_a_guard_passing_the_reserve_does_not_announce_the_pause_over(
    caplog: pytest.LogCaptureFixture,
) -> None:
    venue = _Venue()
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")
    venue.at_weight(_SOFT_LINE)

    venue.guard_reads()

    assert not [r for r in caplog.records if r.levelno == logging.INFO], (
        "routine requests are still held: the pause is not over"
    )


def test_a_429_inside_the_reserve_is_told_with_its_own_end_not_the_reserves(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The guards are sent again when the exchange's 10 s are over; the WARNING must not say 41 s."""
    venue = _Venue()
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")
    venue.at_weight(_SOFT_LINE)
    venue.exchange.failure = rate_limited(429, retry_after="10")

    with (
        prioritised(RequestPriority.EXIT_GUARD),
        pytest.raises(RateLimitedApiException),
    ):
        venue.session.futures_position_information()

    pause = [
        r.getMessage() for r in caplog.records if "[rate-limit-pause]" in r.getMessage()
    ]
    assert len(pause) == 1 and "no request is sent for 10 s" in pause[0], pause
    venue.exchange.failure = None
    venue.advance(11.0)
    assert venue.guard_reads() == ["positions", "mark", "stops"], (
        "the guards are served again 11 s later, as the line said"
    )


def test_a_reserve_met_during_an_exchange_pause_does_not_promise_the_guards_pass(
    caplog: pytest.LogCaptureFixture,
) -> None:
    venue = _Venue()
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")
    venue.gate.block(10.0)

    venue.at_weight(_SOFT_LINE)

    (reserve,) = [
        r.getMessage()
        for r in caplog.records
        if "[rate-limit-reserve]" in r.getMessage()
    ]
    assert "except while a pause of the exchange's own runs" in reserve

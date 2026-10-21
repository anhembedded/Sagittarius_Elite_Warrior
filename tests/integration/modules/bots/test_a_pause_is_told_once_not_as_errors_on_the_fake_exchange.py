"""`BUG-247` - the exchange's pause is one WARNING for the venue, never an ERROR per bot read.

@details The owner's VPS wrote about 200 ERROR lines a day with full tracebacks for a pause the app
had already told once (`Used weight ... [rate-limit-soft]`): the mark price of every bot, the
position of every bot, the open protective stops. A handled pause is not an error and would fail
the run-log scan (`ci-rule.md` §3). The pause here is the exchange's own answer (a queued 429), met
by two running Futures bots on their beats."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .crowd_bots_world import FUTURES_SYMBOLS, run_bots
from .grid_fake_exchange import FakeExchange
from .two_venues_bots_world import FUTURES, booted_two_venues

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from fake_exchange.server import FaultAnswer

PAUSE_SECONDS = 30
BEATS = 6


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []
        self._marked = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def lines(self, *levels: int) -> list[str]:
        return [r.getMessage() for r in self.records if r.levelno in levels]

    def mark(self) -> None:
        self._marked = len(self.records)

    def lines_before_mark(self, *levels: int) -> list[str]:
        return [
            r.getMessage() for r in self.records[: self._marked] if r.levelno in levels
        ]

    def lines_after_mark(self, *levels: int) -> list[str]:
        return [
            r.getMessage() for r in self.records[self._marked :] if r.levelno in levels
        ]


@contextmanager
def _captured() -> Iterator[_Capture]:
    capture = _Capture()
    root = logging.getLogger("App")
    root.addHandler(capture)
    try:
        yield capture
    finally:
        root.removeHandler(capture)


def _meet_a_pause(both_venues: FakeExchange, *, beats: int, then: int = 0) -> _Capture:
    """Two running bots, the exchange's 429 on the next mark read, `beats` beats; the log is
    marked after them, so `then` more beats can be asked what they added (`new_lines`)."""
    with booted_two_venues(both_venues) as app:
        run_bots(app, FUTURES, FUTURES_SYMBOLS[:2])
        both_venues.urls.faults.queued.append(
            FaultAnswer(
                "/fapi/v1/premiumIndex",
                status=429,
                body={"code": -1003, "msg": "Too many requests."},
                headers={"Retry-After": str(PAUSE_SECONDS)},
            )
        )
        with _captured() as log:
            for _ in range(beats):
                app.monotonic.advance(5)
                app.ticker.fire()
            log.mark()
            for _ in range(then):
                app.monotonic.advance(5)
                app.ticker.fire()
    return log


def test_two_bots_meeting_a_pause_on_their_beats_write_no_error(
    both_venues: FakeExchange, weight_gate_lifted: None
) -> None:
    log = _meet_a_pause(both_venues, beats=BEATS)

    errors = log.lines(logging.ERROR, logging.CRITICAL)
    assert errors == [], "a handled pause is not an error:\n" + "\n".join(errors)


def test_the_warnings_of_a_pause_do_not_grow_with_the_beats_it_lasts(
    both_venues: FakeExchange, weight_gate_lifted: None
) -> None:
    """One WARNING for the venue (the gate's) and, for each bot, the consequence told once when
    its reads begin to fail; the beats after that are DEBUG."""
    log = _meet_a_pause(both_venues, beats=2, then=BEATS)

    told = log.lines_before_mark(logging.WARNING)
    assert sum("[rate-limit-pause]" in line for line in told) == 1, told
    assert log.lines_after_mark(logging.WARNING) == []

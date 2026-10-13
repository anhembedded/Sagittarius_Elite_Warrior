"""`EPIC-038D` - the host's health machinery over fourteen simulated days.

The task's soak, as far as it can be run without fourteen days: `tests/health_soak.py` drives the
real snapshot, section, probe, line and file machinery for 14 x 1 440 intervals of 60 s on a clock
it advances, through a user stream that dies at every 24 h boundary and ten-minute outages on two
days in which the exchange answers nothing. It runs as a program in its own interpreter (the module
says why) and this test asserts on what it reports:

  · the health line **never skips an interval** - 20 160 intervals, 20 160 lines;
  · it **says the truth** while it happens - the feed's age climbs to the ten minutes, the clock skew
    is unknown while the exchange is dead and known again after, the stream's down time climbs and
    returns to zero;
  · **nothing grows** - live objects, threads and resident memory are the same on day 14 as on day 2
    (within a stated tolerance), and the snapshot file is always one whole file.

What it is not: a 14-day run of the process. The Scheduler, the bots' workers and the exchange's
websocket are not in it, and no wall-clock time is spent beyond the CPU the loop takes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.health_soak import RESULT_TAG, SoakResult

_REPO_PARENT = Path(__file__).resolve().parents[4].parent
_BUDGET_SECONDS = 300

#: The soak takes about half a minute of CPU in its own interpreter; the global per-test
#: timeout (`pyproject.toml`) is sized for tests that do not, and counts the fixture.
pytestmark = pytest.mark.timeout(_BUDGET_SECONDS + 60)

#: Tolerances, not targets. The soak keeps 20 160 log lines of its own (about 4 MB) to read
#: back, so the resident bound is wider than the machinery needs.
RESIDENT_GROWTH_BOUND_MB = 8
OBJECT_GROWTH_BOUND = 500
THREAD_GROWTH_BOUND = 2
OUTAGE_MINUTES = 10


@pytest.fixture(scope="module")
def soak() -> SoakResult:
    completed = subprocess.run(
        [sys.executable, "-m", "Sagittarius_Elite_Warrior.tests.health_soak"],
        cwd=str(_REPO_PARENT),
        capture_output=True,
        text=True,
        timeout=_BUDGET_SECONDS,
        check=False,
        env={**os.environ, "PYTHONPATH": str(_REPO_PARENT)},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    reported = next(
        line for line in completed.stdout.splitlines() if line.startswith(RESULT_TAG)
    )
    return SoakResult(**json.loads(reported[len(RESULT_TAG) :]))


def test_the_health_line_never_skips_an_interval(soak: SoakResult) -> None:
    assert soak.ticks == 14 * 1440 == 20_160
    assert soak.lines == soak.ticks, "the health line skipped an interval"
    assert soak.snapshot_is_current


def test_it_says_the_truth_while_the_stream_dies_and_the_exchange_goes_dark(
    soak: SoakResult,
) -> None:
    assert soak.outage_ticks == 2 * OUTAGE_MINUTES
    assert soak.max_tick_age_s == OUTAGE_MINUTES * 60, (
        "the feed's age climbed to ten minutes"
    )
    assert soak.skew_was_unknown, "a dead exchange leaves the skew unknown, not stale"
    assert soak.last_skew_ms == 7, "and it is known again once the exchange answers"
    assert soak.max_stream_down_s > 0
    assert soak.last_stream_down_s == 0


def test_nothing_the_host_does_each_interval_grows(soak: SoakResult) -> None:
    assert soak.objects["14"] - soak.objects["2"] < OBJECT_GROWTH_BOUND, soak.objects
    if soak.resident_mb:  # `na` where /proc is absent
        assert (
            soak.resident_mb["14"] - soak.resident_mb["2"] < RESIDENT_GROWTH_BOUND_MB
        ), soak.resident_mb
    assert soak.threads_at_end <= soak.threads_at_start + THREAD_GROWTH_BOUND
    assert soak.files == ["health.json"], (
        "the snapshot is one whole file, no stray temp"
    )

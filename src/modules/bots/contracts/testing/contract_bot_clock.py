"""The contract suite for `IBotClock` (HLD §10.3).

What the consumers rely on: an instant that is timezone-aware and in UTC,
because `run_started_at` is compared with exchange execution times (ADR D6),
which Binance reports in UTC; a naive or local time would shift the run's
window by the machine's offset.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock


class BotClockContract:
    """Inherit this and provide `impl`."""

    @pytest.fixture
    def impl(self) -> IBotClock:
        raise NotImplementedError

    def test_now_is_aware_and_in_utc(self, impl: IBotClock) -> None:
        now = impl.now()
        assert now.tzinfo is not None
        assert now.utcoffset() == timedelta(0)

    def test_now_never_goes_backwards(self, impl: IBotClock) -> None:
        first = impl.now()
        assert impl.now() >= first

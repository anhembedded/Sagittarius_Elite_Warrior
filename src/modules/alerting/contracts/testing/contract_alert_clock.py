"""The contract suite for `IAlertClock` (HLD §10.3).

What the consumers rely on: an instant that is timezone-aware and in UTC (alerts
are stored and compared as UTC), and that never goes backwards (a retry time
computed from it must not move earlier).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)


class AlertClockContract:
    """Inherit this and provide `impl`."""

    @pytest.fixture
    def impl(self) -> IAlertClock:
        raise NotImplementedError

    def test_now_is_aware_and_in_utc(self, impl: IAlertClock) -> None:
        now = impl.now()
        assert now.tzinfo is not None
        assert now.utcoffset() == timedelta(0)

    def test_now_never_goes_backwards(self, impl: IAlertClock) -> None:
        first = impl.now()
        assert impl.now() >= first

"""The contract suite for `IBotRetryScheduler` (HLD §10.3).

What the consumers rely on: a scheduled task runs once, and nothing scheduled
runs after `close()` — so a bot's worker is never posted to after module
shutdown closed it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)


class BotRetrySchedulerContract:
    """Inherit this and provide `impl` and `release`."""

    @pytest.fixture
    def impl(self) -> IBotRetryScheduler:
        raise NotImplementedError

    @pytest.fixture
    def release(self, impl: IBotRetryScheduler) -> Callable[[], None]:
        """Make every task scheduled so far due, and wait until it has run."""
        raise NotImplementedError

    def test_a_scheduled_task_runs_exactly_once(
        self, impl: IBotRetryScheduler, release: Callable[[], None]
    ) -> None:
        ran: list[int] = []

        impl.after(timedelta(0), lambda: ran.append(1))
        release()
        release()

        assert ran == [1]

    def test_nothing_scheduled_runs_after_close(
        self, impl: IBotRetryScheduler, release: Callable[[], None]
    ) -> None:
        ran: list[int] = []
        impl.after(timedelta(hours=1), lambda: ran.append(1))

        impl.close()
        impl.after(timedelta(0), lambda: ran.append(2))
        release()

        assert ran == []

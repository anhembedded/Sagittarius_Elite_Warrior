"""What a Backtest failure must tell the user, asserted once (`BOT-169`).

A presenter test reads the notifier the presenter was built with
(`presenter._failures.notifier`, a `RecordingNotifier` in these tests), so the
check is the same wherever a failure is provoked.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
)


def last_notice(presenter) -> FailureNotice:
    return presenter._failures.notifier.last


def assert_command_notice(presenter, cause: str, detail: str) -> None:
    """The user ran a command and it failed: a modal notice for `cause`, the
    technical text only as `detail`, never in the headline, nothing to retry."""
    notice = last_notice(presenter)
    assert notice.kind is FailureKind.COMMAND
    assert notice.cause == cause
    assert notice.detail == detail
    assert notice.headline
    assert detail not in notice.headline
    assert notice.retry is None

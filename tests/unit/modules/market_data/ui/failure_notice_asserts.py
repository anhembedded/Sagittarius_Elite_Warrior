"""`BOT-169` — the one assertion every Database-screen failure test shares."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
)
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.database_screen import (
    DATABASE_ROUTE,
)

EXCEPTION_TEXT = "EXCEPTION_TEXT-502-Bad-Gateway"


def assert_told_once(
    notifier: RecordingNotifier, kind: FailureKind, cause: str
) -> FailureNotice:
    """One notice of `kind` and `cause`, whose headline is a sentence (no
    exception text) and whose detail holds the exception's text."""
    assert len(notifier.failures) == 1
    notice = notifier.last
    assert (notice.kind, notice.cause) == (kind, cause)
    assert EXCEPTION_TEXT not in notice.headline
    assert EXCEPTION_TEXT in notice.detail
    if kind is FailureKind.BACKGROUND:
        assert notice.scope == DATABASE_ROUTE
    return notice


def assert_log_list_has_no_exception_text(*lists: object) -> None:
    """None of the screen's log-list signals (Mocks) was handed the exception text."""
    for signal in lists:
        for call in signal.call_args_list:  # type: ignore[attr-defined]
            assert EXCEPTION_TEXT not in str(call.args)

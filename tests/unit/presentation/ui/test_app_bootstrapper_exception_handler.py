"""
`BUG-048` regression — `_install_exception_handler`'s `sys.excepthook` must
never block under a headless Qt platform.

`QDialog.exec()` is modal: nothing dismisses it without a human and a real
window manager. Under `QT_QPA_PLATFORM=offscreen` — this project's own
test/CI platform — that human does not exist, so the dialog blocked forever
instead of letting the process exit. Confirmed by fault injection in
`tests/sanity/test_self_check_process.py` (a real subprocess, ~15-30s per
run); this module proves the same fix directly against the handler, in
milliseconds, so the mechanism has fast coverage and the subprocess test
stays reserved for what only it can prove (the real process boundary).
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper import (
    _install_exception_handler,
)


@pytest.fixture(autouse=True)
def _restore_excepthook():
    """`_install_exception_handler` mutates `sys.excepthook` process-wide —
    restore it so this module can't leak into any test that runs after it."""
    original = sys.excepthook
    yield
    sys.excepthook = original


@pytest.fixture(autouse=True)
def _no_real_dialog():
    """Patches `CriticalErrorDialog` for every test in this module,
    unconditionally — including tests exercising the *unfixed* shape of the
    handler, which for real would construct a real modal `QDialog` and call
    `.exec()` on it under `offscreen`, hanging the test process exactly the
    way `BUG-048` hung the real one. A hanging regression test is worse than
    a failing one: it does not fail loudly, it stalls CI. Every test that
    cares whether the dialog was shown asserts against this mock instead of
    letting a real one exist."""
    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper.CriticalErrorDialog"
    ) as dialog_cls:
        yield dialog_cls


def _raise_and_capture_hook() -> None:
    """Installs the handler, then calls the *installed* `sys.excepthook`
    directly with a real exception's info — exercising precisely what an
    uncaught exception in production would trigger, without needing one to
    actually escape in this test's own process."""
    try:
        raise RuntimeError("probe")
    except RuntimeError:
        exc_type, exc_value, exc_tb = sys.exc_info()
    sys.excepthook(exc_type, exc_value, exc_tb)


def test_handler_does_not_show_a_dialog_under_a_headless_platform(
    qapp, _no_real_dialog
):
    """The regression itself: on `offscreen` (this test's own platform —
    every test in this suite runs under it), no dialog may be constructed,
    since nothing could ever dismiss one."""
    _install_exception_handler(app_engine=MagicMock())

    _raise_and_capture_hook()

    _no_real_dialog.assert_not_called()


def test_handler_still_logs_under_a_headless_platform(qapp, _no_real_dialog):
    """The fix must not turn a silent hang into an equally silent no-op —
    the log line is the only report a headless session gets."""
    engine = MagicMock()
    _install_exception_handler(app_engine=engine)

    _raise_and_capture_hook()

    engine.context.logger.error.assert_called_once()
    logged = engine.context.logger.error.call_args[0][0]
    assert "probe" in logged


def test_handler_shows_a_dialog_when_a_real_display_session_exists(
    qapp, _no_real_dialog
):
    """Not a blanket "never show the dialog" — only headless is special-cased.
    A real interactive session should keep getting the dialog; simulated here
    by patching the platform check rather than an actual display, which this
    CI environment does not have. `CriticalErrorDialog` itself stays patched
    by `_no_real_dialog` regardless — this test only asserts it *was*
    constructed and `.exec()` was called, never lets a real one run."""
    _install_exception_handler(app_engine=MagicMock())

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper."
        "is_headless_qt_platform",
        return_value=False,
    ):
        _raise_and_capture_hook()

    _no_real_dialog.assert_called_once()
    _no_real_dialog.return_value.exec.assert_called_once()

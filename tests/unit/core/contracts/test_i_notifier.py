"""`BOT-169` — what every `INotifier` and `failure_detail` promise."""

from __future__ import annotations

import logging

import pytest
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    MAX_DETAIL_CHARS,
    FailureKind,
    FailureNotice,
    INotifier,
    failure_detail,
    failure_signature,
)
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.notifier import NotifierPresenter
from Sagittarius_Elite_Warrior.src.shell.logging_notifier import LoggingNotifier


def _notice() -> FailureNotice:
    return FailureNotice(FailureKind.BACKGROUND, "a.b", "Could not read it.", "trade")


@pytest.fixture(params=["recording", "logging", "qt"])
def notifier(request: pytest.FixtureRequest, qapp: QApplication) -> INotifier:
    if request.param == "recording":
        return RecordingNotifier()
    if request.param == "logging":
        return LoggingNotifier()
    return NotifierPresenter()


def test_every_implementation_satisfies_the_port(notifier: INotifier) -> None:
    assert isinstance(notifier, INotifier)


def test_every_implementation_takes_each_call_without_raising(
    notifier: INotifier,
) -> None:
    notifier.report_failure(_notice())
    notifier.clear_failure("a.b")
    notifier.notify("Bot grid-1 stopped.")


def test_the_recording_notifier_keeps_what_it_was_told() -> None:
    recording = RecordingNotifier()

    recording.report_failure(_notice())
    recording.clear_failure("a.b")
    recording.notify("Bot grid-1 stopped.", "stop loss")

    assert recording.last == _notice()
    assert recording.failures_of(FailureKind.COMMAND) == []
    assert recording.cleared == ["a.b"]
    assert recording.events == [("Bot grid-1 stopped.", "stop loss")]


def test_a_headless_run_logs_what_it_cannot_show(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="App.Shell.Notifier"):
        LoggingNotifier().report_failure(_notice())

    assert "a.b" in caplog.text and "Could not read it." in caplog.text


def test_failure_detail_is_the_message_on_one_line() -> None:
    assert failure_detail(ValueError("bad\n  value\tgiven")) == "bad value given"


def test_failure_detail_of_an_exception_with_no_message_is_its_type() -> None:
    assert failure_detail(TimeoutError()) == "TimeoutError"


def test_failure_detail_is_cut_to_a_bound() -> None:
    detail = failure_detail(RuntimeError("x" * (MAX_DETAIL_CHARS * 2)))

    assert len(detail) == MAX_DETAIL_CHARS + 1
    assert detail.endswith("…")


@pytest.mark.parametrize(
    "detail",
    [
        "the exchange is unavailable (HTTP 502 Bad Gateway)",
        "Spot active symbols could not be read: the exchange is unavailable (HTTP 502)",
        "APIError(code=0): Invalid JSON error message from Binance: <html>",
    ],
)
def test_every_way_of_saying_the_exchange_did_not_answer_is_one_signature(
    detail: str,
) -> None:
    assert failure_signature(detail) == failure_signature(
        "the exchange is unavailable (HTTP 503)"
    )


def test_other_texts_are_their_own_signature_and_an_empty_one_stays_empty() -> None:
    assert failure_signature("-2015") == "-2015"
    assert failure_signature("-2015") != failure_signature("-1021")
    assert failure_signature("") == ""

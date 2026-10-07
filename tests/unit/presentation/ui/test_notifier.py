"""`BOT-169` — `NotifierPresenter` picks the surface for a message, once per cause."""

from __future__ import annotations

import threading
from collections.abc import Callable

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.notifier import (
    NotifierPresenter,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.message_bar import MessageBarHost


def _notice(
    kind: FailureKind = FailureKind.BACKGROUND,
    cause: str = "trading.spot.account",
    headline: str = "Could not read the account. Check the connection.",
    scope: str = "trade",
    detail: str | None = None,
    retry: Callable[[], None] | None = None,
) -> FailureNotice:
    # Each cause has a text of its own unless a test says two share one.
    text = f"detail of {cause}" if detail is None else detail
    return FailureNotice(kind, cause, headline, scope, text, retry)


class _Boxes:
    """A box factory that records the boxes instead of letting them open."""

    def __init__(self) -> None:
        self.made: list[QMessageBox] = []

    def __call__(self, notice: FailureNotice, parent: QWidget | None) -> QMessageBox:
        box = QMessageBox(
            QMessageBox.Icon.Critical,
            "t",
            notice.headline,
            QMessageBox.StandardButton.Ok,
        )
        box.open = lambda: None  # type: ignore[method-assign]
        self.made.append(box)
        return box


@pytest.fixture
def boxes() -> _Boxes:
    return _Boxes()


@pytest.fixture
def host(qapp: QApplication) -> MessageBarHost:
    return MessageBarHost()


@pytest.fixture
def notifier(
    qapp: QApplication, boxes: _Boxes, host: MessageBarHost
) -> NotifierPresenter:
    presenter = NotifierPresenter(boxes)
    presenter.register_scope("trade", host)
    return presenter


def test_it_is_an_inotifier(notifier: NotifierPresenter) -> None:
    assert isinstance(notifier, INotifier)


def test_a_failed_command_is_one_message_box_never_a_bar(
    notifier: NotifierPresenter, boxes: _Boxes, host: MessageBarHost
) -> None:
    notifier.report_failure(_notice(FailureKind.COMMAND, cause="trading.order"))

    assert len(boxes.made) == 1
    assert boxes.made[0].text().startswith("Could not read")
    assert host.causes() == ()


def test_a_burst_of_one_failed_command_opens_one_box(
    notifier: NotifierPresenter, boxes: _Boxes
) -> None:
    for _ in range(4):
        notifier.report_failure(_notice(FailureKind.COMMAND, cause="trading.order"))

    assert len(boxes.made) == 1


def test_a_second_cause_gets_its_own_box_and_a_closed_one_may_open_again(
    notifier: NotifierPresenter, boxes: _Boxes
) -> None:
    notifier.report_failure(_notice(FailureKind.COMMAND, cause="a"))
    notifier.report_failure(_notice(FailureKind.COMMAND, cause="b"))
    boxes.made[0].finished.emit(0)
    notifier.report_failure(_notice(FailureKind.COMMAND, cause="a"))

    assert len(boxes.made) == 3


def test_a_background_failure_is_a_bar_in_its_mode_and_no_box(
    notifier: NotifierPresenter, boxes: _Boxes, host: MessageBarHost
) -> None:
    notifier.report_failure(_notice())

    assert host.causes() == ("trading.spot.account",)
    bar = host.bar("trading.spot.account")
    assert bar is not None
    assert bar.headline.startswith("Could not read the account")
    assert boxes.made == []


def test_one_outage_read_four_times_is_one_bar(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    """The 2026-10-07 Spot Testnet outage: four failed reads within 50 ms."""
    for _ in range(4):
        notifier.report_failure(_notice())

    assert host.causes() == ("trading.spot.account",)
    assert host.bar_count() == 1


def test_a_different_failure_a_moment_later_is_never_hidden_in_the_outage_bar(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    """The outage's reads and then a refused key within the same second: the
    key is a different failure, so it keeps its own bar, headline and detail."""
    notifier.report_failure(_notice(cause="a", headline="Account could not be read."))
    notifier.report_failure(
        _notice(cause="key", headline="Your API key was rejected.", detail="-2015")
    )

    assert host.bar_count() == 2
    key_bar = host.bar("key")
    assert key_bar is not None and key_bar.headline == "Your API key was rejected."


def test_four_reads_failing_with_one_text_are_one_bar(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    """One outage: the planner, the fills, the list and the account each fail
    with the exchange's one sentence. That is one message, not four."""
    sentence = "the exchange is unavailable (HTTP 502 Bad Gateway)"
    for cause in ("bots.planner", "bots.fills", "bots.list", "trading.account"):
        notifier.report_failure(_notice(cause=cause, detail=sentence))

    assert host.bar_count() == 1
    assert set(host.causes()) == {
        "bots.planner",
        "bots.fills",
        "bots.list",
        "trading.account",
    }


def test_a_merged_bar_stays_until_every_cause_on_it_recovered(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    for cause in ("a", "b"):
        notifier.report_failure(_notice(cause=cause, detail="HTTP 502"))

    notifier.clear_failure("a")
    assert host.bar_count() == 1

    notifier.clear_failure("b")
    assert host.bar_count() == 0


def test_when_the_cause_a_bar_shows_recovers_it_shows_the_next_with_its_own_controls(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    calls: list[str] = []
    notifier.report_failure(_notice(cause="a", headline="First.", detail="HTTP 502"))
    notifier.report_failure(
        _notice(
            cause="b",
            headline="Second.",
            detail="HTTP 502",
            retry=lambda: calls.append("b"),
        )
    )

    notifier.clear_failure("a")

    bar = host.bar("b")
    assert bar is not None and bar.headline == "Second."
    assert not bar._retry.isHidden()
    bar._retry.click()
    assert calls == ["b"]


def test_retry_on_a_merged_bar_retries_every_cause_on_it(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    calls: list[str] = []
    for cause in ("a", "b"):
        notifier.report_failure(
            _notice(
                cause=cause, detail="HTTP 502", retry=lambda c=cause: calls.append(c)
            )
        )
    bar = host.bar("a")
    assert bar is not None

    bar._retry.click()

    assert calls == ["a", "b"]


def test_a_cause_that_recovers_and_fails_again_never_leaves_a_dead_bar(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    notifier.report_failure(_notice(cause="a", detail="HTTP 502"))
    notifier.report_failure(_notice(cause="b", detail="HTTP 502"))
    notifier.clear_failure("a")
    notifier.report_failure(_notice(cause="a", detail="HTTP 502"))

    notifier.clear_failure("a")
    notifier.clear_failure("b")

    assert host.bar_count() == 0
    assert host.layout().count() == 0


def test_dismissing_a_merged_bar_removes_every_cause_on_it(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    for cause in ("a", "b"):
        notifier.report_failure(_notice(cause=cause, detail="HTTP 502"))
    bar = host.bar("a")
    assert bar is not None

    bar._dismiss.click()

    assert host.causes() == ()


def test_failures_with_different_texts_in_one_mode_stay_separate_bars(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    notifier.report_failure(_notice(cause="a", detail="HTTP 502"))
    notifier.report_failure(_notice(cause="b", detail="HTTP 429 rate limit"))

    assert host.bar_count() == 2


def test_a_failure_with_no_technical_text_is_never_merged(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    notifier.report_failure(_notice(cause="a", detail=""))
    notifier.report_failure(_notice(cause="b", detail=""))

    assert host.bar_count() == 2


def test_a_changed_headline_for_the_same_cause_updates_the_bar_in_place(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    notifier.report_failure(_notice(headline="first"))
    notifier.report_failure(_notice(headline="second"))

    bar = host.bar("trading.spot.account")
    assert bar is not None and bar.headline == "second"
    assert host.bar_count() == 1


def test_two_causes_are_two_bars_and_a_recovery_removes_only_its_own(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    notifier.report_failure(_notice(cause="a"))
    notifier.report_failure(_notice(cause="b"))

    notifier.clear_failure("a")

    assert host.causes() == ("b",)
    notifier.clear_failure("b")
    assert host.causes() == ()
    assert not host.isVisibleTo(host.parentWidget() or host)


def test_the_bar_offers_retry_only_when_the_notice_has_one(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    calls: list[str] = []
    notifier.report_failure(_notice(cause="with", retry=lambda: calls.append("retry")))
    notifier.report_failure(_notice(cause="without"))

    with_retry = host.bar("with")
    without = host.bar("without")
    assert with_retry is not None and without is not None
    assert not with_retry._retry.isHidden()
    assert without._retry.isHidden()
    with_retry._retry.click()
    assert calls == ["retry"]


def test_details_is_offered_only_when_there_is_technical_text(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    notifier.report_failure(_notice(cause="with", detail="HTTP 502"))
    notifier.report_failure(_notice(cause="without", detail=""))

    with_detail = host.bar("with")
    without = host.bar("without")
    assert with_detail is not None and without is not None
    assert not with_detail._details.isHidden()
    assert without._details.isHidden()


def test_dismissing_a_bar_removes_it(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    notifier.report_failure(_notice())
    bar = host.bar("trading.spot.account")
    assert bar is not None

    bar._dismiss.click()

    assert host.causes() == ()


def test_a_failure_with_no_mode_is_shown_in_the_mode_showing(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    notifier.show_unscoped_in("trade")

    notifier.report_failure(_notice(scope=""))

    assert host.causes() == ("trading.spot.account",)


def test_a_bar_text_is_plain_text_even_when_it_looks_like_markup(
    notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    notifier.report_failure(_notice(headline="<h1>502 Bad Gateway</h1>"))

    bar = host.bar("trading.spot.account")
    assert bar is not None
    assert bar.headline == "<h1>502 Bad Gateway</h1>"
    assert bar._headline.textFormat().name == "PlainText"


def test_an_event_without_a_tray_is_shown_in_the_status_bar(
    qapp: QApplication, boxes: _Boxes
) -> None:
    window = QMainWindow()
    presenter = NotifierPresenter(boxes)
    presenter.attach_window(window)

    presenter.notify("Bot grid-1 stopped on its stop loss")

    assert window.statusBar().currentMessage() == "Bot grid-1 stopped on its stop loss"
    window.deleteLater()


def test_a_failure_told_from_a_worker_thread_lands_on_the_ui_thread(
    qapp: QApplication, notifier: NotifierPresenter, host: MessageBarHost
) -> None:
    worker = threading.Thread(target=lambda: notifier.report_failure(_notice()))
    worker.start()
    worker.join()
    assert host.causes() == ()  # queued: nothing touched a widget off-thread

    qapp.processEvents()

    assert host.causes() == ("trading.spot.account",)

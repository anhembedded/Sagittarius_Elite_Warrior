"""`BOT-178` — the Engine's per-dispatch `Executing query:` line is developer detail.

The Engine's `Dispatcher` writes `Executing query: <name>` at INFO for every
dispatch, and the desktop polls (bots status every 10 s, connection checks), so
a normal run's log filled with lines that bury fills, orders and warnings. The
Engine is not changed here (`ONBOARDING.md` §2); the app decides what its own
`App` logger lets through. These tests dispatch through the real composition
root and the Engine's real `Dispatcher`, so they fail if the line moves or the
filter stops being installed (`CS-002`).

Retire when: the Engine logs the query line at DEBUG (the patch in `BOT-178`),
and `shell/dispatch_log_filter.py` goes with it.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.shell.dispatch_log_filter import (
    PausedCallFailureFilter,
    QueryDispatchFilter,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_error_codes import (
    EXCHANGE_PAUSE_TAG,
)
from sagittarius_engine import App
from sagittarius_engine.extensions.cqrs import ICommand, IQuery
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_DEV_MODE_KEY = "dev.mode"


class PollStatusQuery(IQuery):
    def execute(self, dto: object) -> str:
        return "status"


class FailingStatusQuery(IQuery):
    def execute(self, dto: object) -> str:
        raise RuntimeError("exchange did not answer")


class PausedStatusQuery(IQuery):
    """A poll the exchange's pause refuses, worded as `RateLimitedApiException` words it."""

    def execute(self, dto: object) -> str:
        raise RuntimeError(
            f"APIError(code=-1003): no request is sent for another 32 s {EXCHANGE_PAUSE_TAG}"
        )


class StartBotCommand(ICommand):
    def execute(self, dto: object) -> str:
        return "started"


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def lines(self, level: int) -> list[str]:
        return [r.getMessage() for r in self.records if r.levelno == level]


@pytest.fixture
def captured() -> Iterator[_Capture]:
    """`create_app` rewires the process-wide `App` logger; put it back."""
    logger = logging.getLogger("App")
    handlers, level = list(logger.handlers), logger.level
    filters, propagate = list(logger.filters), logger.propagate
    capture = _Capture()
    yield capture
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    for handler in handlers:
        logger.addHandler(handler)
    for log_filter in list(logger.filters):
        logger.removeFilter(log_filter)
    for log_filter in filters:
        logger.addFilter(log_filter)
    logger.setLevel(level)
    logger.propagate = propagate


def _app(capture: _Capture, *, developer: bool) -> App:
    config = ConfigManager()
    config.load_dict(
        {_DEV_MODE_KEY: developer, "log.level": "DEBUG" if developer else "INFO"}
    )
    app = create_app(config)
    logging.getLogger("App").addHandler(capture)
    container = app.context.container
    for handler_class in (
        PollStatusQuery,
        FailingStatusQuery,
        PausedStatusQuery,
        StartBotCommand,
    ):
        container.singleton(handler_class, handler_class())
    return app


def test_a_dispatched_query_writes_no_info_record_outside_developer_mode(
    captured: _Capture,
) -> None:
    app = _app(captured, developer=False)

    assert app.dispatch(PollStatusQuery, None) == "status"

    assert captured.lines(logging.INFO) == []


def test_a_dispatched_query_writes_its_info_record_in_developer_mode(
    captured: _Capture,
) -> None:
    app = _app(captured, developer=True)

    app.dispatch(PollStatusQuery, None)

    assert captured.lines(logging.INFO) == ["Executing query: PollStatusQuery"]


def test_a_dispatched_command_still_logs_at_info_outside_developer_mode(
    captured: _Capture,
) -> None:
    app = _app(captured, developer=False)

    app.dispatch(StartBotCommand, None)

    assert captured.lines(logging.INFO) == ["Executing command: StartBotCommand"]


def test_a_failing_query_still_logs_its_error_outside_developer_mode(
    captured: _Capture,
) -> None:
    app = _app(captured, developer=False)

    with pytest.raises(RuntimeError):
        app.dispatch(FailingStatusQuery, None)

    assert captured.lines(logging.ERROR) == [
        "FailingStatusQuery failed: exchange did not answer"
    ]
    assert captured.lines(logging.INFO) == []


def test_a_warning_from_the_app_still_logs_outside_developer_mode(
    captured: _Capture,
) -> None:
    _app(captured, developer=False)

    logging.getLogger("App.Bots").warning("[recovering] bot b1 needs a person")

    assert captured.lines(logging.WARNING) == ["[recovering] bot b1 needs a person"]


def test_the_filter_is_installed_once_however_often_the_graph_is_built(
    captured: _Capture,
) -> None:
    _app(captured, developer=False)
    app = _app(captured, developer=False)
    app.dispatch(PollStatusQuery, None)

    installed = logging.getLogger("App").filters
    assert [type(f) for f in installed].count(QueryDispatchFilter) == 1
    assert [type(f) for f in installed].count(PausedCallFailureFilter) == 1
    assert captured.lines(logging.INFO) == []


@pytest.mark.parametrize(
    ("developer", "expected"),
    [
        (False, "[log-filter] dispatcher query lines hidden (dev.mode off)"),
        (True, "[log-filter] dispatcher query lines shown (dev.mode on)"),
    ],
)
def test_the_decision_is_logged_when_the_graph_is_built(
    captured: _Capture, developer: bool, expected: str
) -> None:
    # `create_app` rebuilds the handlers of `App` itself, so listen on the child.
    child = logging.getLogger("App.LogFilter")
    child.addHandler(captured)
    child.setLevel(logging.DEBUG)
    try:
        config = ConfigManager()
        config.load_dict({_DEV_MODE_KEY: developer})
        create_app(config)
    finally:
        child.removeHandler(captured)
        child.setLevel(logging.NOTSET)

    assert captured.lines(logging.INFO) == [expected]


def test_a_call_the_exchanges_pause_refused_is_not_an_error_outside_developer_mode(
    captured: _Capture,
) -> None:
    """`BUG-216`: the Engine writes `<Query> failed: ...` at ERROR for each poll a pause
    refuses; during the owner's ban that was four lines every five seconds for 90 s."""
    app = _app(captured, developer=False)

    with pytest.raises(RuntimeError):
        app.dispatch(PausedStatusQuery, None)

    assert captured.lines(logging.ERROR) == []
    assert [r.levelno for r in captured.records if "failed" in r.getMessage()] == [
        logging.DEBUG
    ]


def test_a_failure_that_is_not_the_pause_is_still_an_error_whatever_its_text_says(
    captured: _Capture,
) -> None:
    """The demotion keys on the tag the pause's own exception carries, not on its words."""
    app = _app(captured, developer=False)

    with pytest.raises(RuntimeError):
        app.dispatch(FailingStatusQuery, None)

    assert captured.lines(logging.ERROR) == [
        "FailingStatusQuery failed: exchange did not answer"
    ]

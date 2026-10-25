"""`BUG-269` - the Binance client library's records reach the application log.

`python-binance` logs through `logging.getLogger("binance...")`, outside `App.*`, so its ERROR
records (`ConnectionClosedError`, `BinanceWebsocketClosed`, `BinanceWebsocketQueueOverflow`) fell to
Python's unformatted last resort on stderr: no timestamp, in no log file, and beyond the gate's log
scan. The app routes them to `App.BinanceClient` in the standard format, tagged `[binance-client]`,
at WARNING at most: the library's ERROR is a failure it reconnects from itself, and the application
logs a stream it sees dead at ERROR (`BinanceWebsocketService`).

Retire when: the library logs through a logger the app configures.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from Sagittarius_Elite_Warrior.src.shell.binance_client_log import (
    route_binance_client_logs,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_LIBRARY_LOGGER = "binance.ws.reconnecting_websocket"


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def app_log() -> Iterator[_Capture]:
    """The `App` logger as the run configures it, restored afterwards with the library's."""
    app = logging.getLogger("App")
    library = logging.getLogger("binance")
    saved = (list(app.handlers), app.level, app.propagate)
    saved_library = (list(library.handlers), library.propagate, library.level)
    capture = _Capture()
    app.addHandler(capture)
    app.setLevel(logging.DEBUG)
    yield capture
    app.removeHandler(capture)
    app.handlers[:] = saved[0]
    app.setLevel(saved[1])
    app.propagate = saved[2]
    library.handlers[:] = saved_library[0]
    library.propagate = saved_library[1]
    library.setLevel(saved_library[2])


def test_a_library_error_is_an_app_record_tagged_and_capped_at_warning(
    app_log: _Capture,
) -> None:
    route_binance_client_logs()

    logging.getLogger(_LIBRARY_LOGGER).error(
        "ConnectionClosedError (sent 1011 (internal error) keepalive ping timeout)"
    )

    [record] = [r for r in app_log.records if r.name == "App.BinanceClient"]
    assert record.levelno == logging.WARNING
    message = record.getMessage()
    assert message.startswith("[binance-client]")
    assert "keepalive ping timeout" in message
    assert _LIBRARY_LOGGER in message


def test_routing_twice_installs_one_route(app_log: _Capture) -> None:
    route_binance_client_logs()
    route_binance_client_logs()

    logging.getLogger(_LIBRARY_LOGGER).error("Connection closed. Reconnecting...")

    assert len([r for r in app_log.records if r.name == "App.BinanceClient"]) == 1


def test_a_library_record_reaches_no_other_logger_than_the_apps(
    app_log: _Capture,
) -> None:
    """The record is the app's alone: not also the root logger's, whose handlers (or Python's
    last resort, when it has none) would write it a second time, unformatted."""
    root = _Capture()
    logging.getLogger().addHandler(root)
    try:
        route_binance_client_logs()

        logging.getLogger(_LIBRARY_LOGGER).error(
            "Message queue size 100 exceeded maximum 100"
        )
    finally:
        logging.getLogger().removeHandler(root)

    assert [r for r in root.records if r.name.startswith("binance")] == []
    assert len([r for r in app_log.records if r.name == "App.BinanceClient"]) == 1


def test_a_library_debug_record_stays_a_debug_record(app_log: _Capture) -> None:
    route_binance_client_logs()

    logging.getLogger(_LIBRARY_LOGGER).debug("no message in 10 seconds")

    [record] = [r for r in app_log.records if r.name == "App.BinanceClient"]
    assert record.levelno == logging.DEBUG


def test_the_composition_root_routes_the_library_log(app_log: _Capture) -> None:
    """The wiring: a booted app, not the function called by hand (`CS-002`)."""
    from_a_boot = ConfigManager()
    from_a_boot.load_dict({"dev.mode": False, "log.level": "INFO"})
    create_app(from_a_boot)
    logging.getLogger("App").addHandler(app_log)
    logging.getLogger("App").setLevel(logging.DEBUG)

    logging.getLogger(_LIBRARY_LOGGER).error(
        "BinanceWebsocketClosed (Connection closed.)"
    )

    assert [r for r in app_log.records if r.name == "App.BinanceClient"] != []

"""`BUG-270` - the Binance client library's log records go through the application's log.

`python-binance` logs through loggers named `binance.*` (`binance.ws.reconnecting_websocket` says
`ConnectionClosedError`, `BinanceWebsocketClosed` and `BinanceWebsocketQueueOverflow`), outside the
`App.*` namespace every handler of the app is attached to (`logging-rule.md` §1). Its ERROR records
therefore fell to Python's last resort: unformatted on stderr, without a timestamp, in no log file
and beyond the gate's log scan. On the owner's mainnet incident of 2026-10-25 the only trace of the
connection that died was three such lines.

The route is one handler on the library's top logger, `binance`, which re-emits each record on
`App.BinanceClient` with the tag `[binance-client]` and the library's logger name, and stops the
record going anywhere else. The level is the library's, capped at WARNING: the library's ERROR is a
failure it reconnects from by itself (a dropped ping, a closed socket), and a stream the app sees
dead is logged by `BinanceWebsocketService` at ERROR; a library record would otherwise fail every
run-log scan for a reconnect the app survives. A DEBUG record stays DEBUG, so a `--dev` log keeps
the library's detail.

Extension cases (`architecture-rule.md` §7.2.1): another library with its own logger tree is one more
route of the same shape; a different cap is `_LEVEL_CAP`.

Retire when: the library logs through a logger the app configures.
"""

from __future__ import annotations

import logging

_APP_LOGGER = "App.BinanceClient"
_LEVEL_CAP = logging.WARNING

_app_log = logging.getLogger("App.BinanceClient")
_decision_log = logging.getLogger("App.BinanceClientRoute")


class _BinanceClientRoute(logging.Handler):
    """Re-emits a library record on `App.BinanceClient`."""

    def emit(self, record: logging.LogRecord) -> None:
        level = min(record.levelno, _LEVEL_CAP)
        _app_log.log(level, "[binance-client] %s: %s", record.name, record.getMessage())


def route_binance_client_logs() -> None:
    """Send the library's records to the app's log; installing it twice leaves one route."""
    # The library's logger is someone else's: only handlers and levels are managed on it
    # (`logging-rule.md` §1), through the call itself.
    for installed in [
        h
        for h in logging.getLogger("binance").handlers
        if isinstance(h, _BinanceClientRoute)
    ]:
        logging.getLogger("binance").removeHandler(installed)
    logging.getLogger("binance").addHandler(_BinanceClientRoute(logging.DEBUG))
    logging.getLogger("binance").propagate = False
    # The library's detail follows the run's: DEBUG in a `--dev` log, WARNING and up otherwise.
    logging.getLogger("binance").setLevel(logging.getLogger("App").getEffectiveLevel())
    # `logging-rule.md` §2: the decision is logged.
    _decision_log.info(
        "[binance-client] the Binance client library's records go to %s (capped at %s)",
        _APP_LOGGER,
        logging.getLevelName(_LEVEL_CAP),
    )

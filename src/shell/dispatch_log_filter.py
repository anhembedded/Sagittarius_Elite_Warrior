"""The Engine's dispatcher lines the app reshapes: the per-dispatch `Executing query:` line, and the
failure line of a call the exchange's pause refused.

`Dispatcher.dispatch` (Engine, `kernel/dispatcher.py`) logs `Executing query: <name>`
at INFO on the shared `App` logger for every dispatch. The desktop polls (the bots'
status report and list every 10 s, connection checks), so a normal run's log filled
with lines that buried fills, orders and warnings, on the VPS host too (`BOT-178`).

The Engine is not changed from this repository (`ONBOARDING.md` §2): its dispatcher
has no logger of its own to put at DEBUG, only the `App` logger every component
shares, so the app decides what that logger lets through. A record names the query
line by what the Engine attaches to it, `extra={"submodule": "Dispatcher"}`, and by
its `Executing query: ` prefix, the only thing that tells it from the command line
(`Executing command: `), which keeps its level. Failures (`<name> failed`, ERROR) and
payload and completion lines (DEBUG) are not matched.

Retire when: the Engine logs the query line at DEBUG (the patch is in `BOT-178`'s
implementation notes); this module and its installer call go with it.

The second filter is `BUG-217`'s. While the exchange's pause runs (a 429, `-1003`, or the app's
own soft limit), every poll of the desktop is refused at once and the dispatcher writes
`<Query> failed: ...` at ERROR for each: four lines every five seconds for the minute and a half
of the owner's 2026-10-15 ban, none of them news after the one WARNING that began the pause
(`ExchangeCallPolicy`). A failure whose text carries `EXCHANGE_PAUSE_TAG` is written at DEBUG
instead: still in a `--dev` log, off a normal run's. A command refused by the pause (a manual order) is
demoted too, on purpose: the desk tells its user of the refusal as a command failure, and the pause
itself is a WARNING that is told again whenever it is extended or turns into a ban.

Retire when: the Engine lets a handler's exception choose its own log level.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_error_codes import (
    EXCHANGE_PAUSE_TAG,
)
from sagittarius_engine.interfaces.i_config import IConfig

#: What the Engine's `StdLogger` stores `extra=` under, and the dispatcher's tag.
_EXTRA_ATTRIBUTE = "extra"
_DISPATCHER = "Dispatcher"
_QUERY_LINE_PREFIX = "Executing query: "
_FAILED = " failed: "
_decision_log = logging.getLogger("App.LogFilter")


class QueryDispatchFilter(logging.Filter):
    """Drops the Engine's INFO line for a dispatched query."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno != logging.INFO:
            return True
        extra = getattr(record, _EXTRA_ATTRIBUTE, None)
        if not isinstance(extra, dict) or extra.get("submodule") != _DISPATCHER:
            return True
        return not str(record.msg).startswith(_QUERY_LINE_PREFIX)


class PausedCallFailureFilter(logging.Filter):
    """Writes the Engine's ERROR for a call the exchange's pause refused at DEBUG."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno != logging.ERROR:
            return True
        extra = getattr(record, _EXTRA_ATTRIBUTE, None)
        if not isinstance(extra, dict) or extra.get("submodule") != _DISPATCHER:
            return True
        text = str(record.msg)
        if _FAILED in text and EXCHANGE_PAUSE_TAG in text:
            record.levelno = logging.DEBUG
            record.levelname = logging.getLevelName(logging.DEBUG)
        return True


def quiet_query_dispatch_outside_developer_mode(config: IConfig) -> None:
    """Put the filter on the `App` logger unless this run is in developer mode.

    `dev.mode` is true for `--dev`/`--debug` and for the file's switch alike
    (`shell/dev_mode.py`). A filter on the logger, not on a handler, survives
    the Engine rebuilding the handlers (`create_app` builds its logger twice);
    any filter an earlier build left is removed first, so building the graph again
    never stacks it.
    """
    logger = logging.getLogger("App")
    for installed in [
        f
        for f in logger.filters
        if isinstance(f, QueryDispatchFilter | PausedCallFailureFilter)
    ]:
        logger.removeFilter(installed)
    developer = bool(config.get(ConfigKeys.DEV_MODE.value, False))
    if not developer:
        logger.addFilter(QueryDispatchFilter())
    logger.addFilter(PausedCallFailureFilter())
    # `logging-rule.md` §2: the decision is logged, the disabled case included.
    _decision_log.info(
        "[log-filter] dispatcher query lines %s (dev.mode %s)",
        "shown" if developer else "hidden",
        "on" if developer else "off",
    )

"""The Engine's per-dispatch `Executing query:` line, shown only in developer mode.

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
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from sagittarius_engine.interfaces.i_config import IConfig

#: What the Engine's `StdLogger` stores `extra=` under, and the dispatcher's tag.
_EXTRA_ATTRIBUTE = "extra"
_DISPATCHER = "Dispatcher"
_QUERY_LINE_PREFIX = "Executing query: "


class QueryDispatchFilter(logging.Filter):
    """Drops the Engine's INFO line for a dispatched query."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno != logging.INFO:
            return True
        extra = getattr(record, _EXTRA_ATTRIBUTE, None)
        if not isinstance(extra, dict) or extra.get("submodule") != _DISPATCHER:
            return True
        return not str(record.msg).startswith(_QUERY_LINE_PREFIX)


def quiet_query_dispatch_outside_developer_mode(config: IConfig) -> None:
    """Put the filter on the `App` logger unless this run is in developer mode.

    `dev.mode` is true for `--dev`/`--debug` and for the file's switch alike
    (`shell/dev_mode.py`). A filter on the logger, not on a handler, survives
    the Engine rebuilding the handlers (`create_app` builds its logger twice);
    any filter an earlier build left is removed first, so building the graph again
    never stacks it.
    """
    logger = logging.getLogger("App")
    for installed in [f for f in logger.filters if isinstance(f, QueryDispatchFilter)]:
        logger.removeFilter(installed)
    if not config.get(ConfigKeys.DEV_MODE.value, False):
        logger.addFilter(QueryDispatchFilter())

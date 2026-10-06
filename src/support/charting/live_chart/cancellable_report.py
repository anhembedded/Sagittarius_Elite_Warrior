"""How a worker reports to a chart that may be closed meanwhile (`BUG-150`).

A worker thread reports through a Qt signal of the chart that asked it. The
chart is cancelled before it is closed and deleted (a Market tab's chart is
`deleteLater`'d), so a cancelled request reports nothing. Checking the token
first is not enough on its own: the chart can be closed and deleted between
the check and the emit, which then raises `RuntimeError` ("Signal source has
been deleted"). That error is dropped only when the token proves the race;
any other `RuntimeError` still raises.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

logger = logging.getLogger("App.LiveChart")


def report_unless_cancelled[*Args](
    token: CancellationToken, emit: Callable[[*Args], None], *args: *Args
) -> None:
    """Calls `emit(*args)` unless `token` is cancelled, before or during it."""
    if token.is_cancelled():
        return
    try:
        emit(*args)
    except RuntimeError:
        if not token.is_cancelled():
            raise
        logger.debug("[live-chart] a report raced its chart's close and was dropped")

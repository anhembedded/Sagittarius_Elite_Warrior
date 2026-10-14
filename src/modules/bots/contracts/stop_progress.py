"""`EPIC-029E` / `EPIC-039H` — where a run of a Grid's stop ended.

@details It is the answer of `IExposureCloser.close` as well as of the whole stop, so the
closer of a venue profile and the sequence that calls it speak one type. Moved out of
`grid_stop_sequence.py` when the close became a port.
"""

from __future__ import annotations

from enum import Enum


class StopProgress(str, Enum):
    """Where a run of the stop ended: what, if anything, it still waits for."""

    #: STOPPED: zero tagged orders were open.
    STOPPED = "stopped"
    #: STOPPING, on the exchange: a refused cancel, an order not yet gone, a
    #: budget or history read that did not answer. A later run can finish it.
    WAITING_ON_EXCHANGE = "waiting_on_exchange"
    #: STOPPING, on the order session: trading is off, so the switch-on event
    #: runs it again — a timer would only be refused.
    WAITING_FOR_TRADING = "waiting_for_trading"
    #: The bot left STOPPING (a fault, or a halted exit); a stop is asked anew.
    ENDED = "ended"

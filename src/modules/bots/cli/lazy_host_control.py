"""`IHostControl`, looked up when a verb first sends a request (`PRO-014`).

`BotCliHandler` hands every verb the same `BotVerbWorld`, and the world holds the
operator's side of host control, which `operations` binds. `bot list` never sends
anything, so building it before the verb ran made `bot list` need `operations` - and
`operations` needs `alerting` - to print a table. This asks the container at the first
`send`, so a verb that never controls the host never asks, and a command that declares
only `bots` in `cli_commands.json` boots without the others.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl


class LazyHostControl(IHostControl):
    """Sends through the `IHostControl` that `resolve` returns, resolved on each call."""

    def __init__(self, resolve: Callable[[], IHostControl]) -> None:
        self._resolve = resolve

    def send(self, request: HostControlRequest, wait_s: float) -> HostControlReply:
        return self._resolve().send(request, wait_s)

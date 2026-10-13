"""The `run` host's states and the moves between them (`DESIGN_2026-10-09_headless_operation.md` §6).

    BOOTING -> SERVING -> DRAINING -> STOPPED
    BOOTING | SERVING | DRAINING -> FAILED

`STOPPED` and `FAILED` are final. The table is the whole of the lifecycle:
`RunHost` asks `HostStateMachine.move_to` and learns, from the same place, what
the move is and whether it is allowed. A move the table does not list raises, so a
code path that skips a state (SERVING straight to STOPPED, a second drain) is a
failing test, not a surprise in production.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)

logger = logging.getLogger("App.Operations.Host")

_MOVES: dict[HostState, frozenset[HostState]] = {
    HostState.BOOTING: frozenset({HostState.SERVING, HostState.FAILED}),
    HostState.SERVING: frozenset({HostState.DRAINING, HostState.FAILED}),
    HostState.DRAINING: frozenset({HostState.STOPPED, HostState.FAILED}),
    HostState.STOPPED: frozenset(),
    HostState.FAILED: frozenset(),
}


class InvalidHostMoveError(RuntimeError):
    def __init__(self, source: HostState, target: HostState) -> None:
        super().__init__(f"the host cannot go from {source.value} to {target.value}")
        self.source = source
        self.target = target


class HostStateMachine:
    def __init__(self) -> None:
        self._state = HostState.BOOTING

    @property
    def state(self) -> HostState:
        return self._state

    @property
    def is_final(self) -> bool:
        return not _MOVES[self._state]

    def move_to(self, target: HostState, reason: str = "") -> None:
        """One INFO line per move, naming both ends and (for a failure) why."""
        if target not in _MOVES[self._state]:
            raise InvalidHostMoveError(self._state, target)
        logger.info(
            "[host] %s -> %s%s",
            self._state.value,
            target.value,
            f": {reason}" if reason else "",
        )
        self._state = target

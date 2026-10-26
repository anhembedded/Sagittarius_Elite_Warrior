"""`EPIC-047A` — a receiver applies a bot's record only when its revision is greater.

A snapshot read at revision 3 can arrive after the event at revision 4 that overtook it. The
gate keeps, per bot, the greatest revision seen and the value that carried it, and refuses a
lesser or equal one, so any order of arrival leaves the same state. A deletion is a value of
`None` at its own revision and is remembered, so a late snapshot cannot bring the bot back.

The gate only compares numbers. Where a revision comes from (a counter the host keeps, the bridge's
own sequence) is the sender's choice, made in `EPIC-047C`; the codec carries it in the message
envelope (`WireRoots.encode(..., revision=n)`, `revision_of`).
"""

from __future__ import annotations


class RevisionGate[T]:
    """The latest value per bot id, by revision."""

    def __init__(self) -> None:
        self._latest: dict[str, tuple[int, T | None]] = {}

    def offer(self, bot_id: str, revision: int, value: T | None) -> bool:
        """Apply `value` if `revision` is greater than the one held; `None` records a deletion."""
        if type(revision) is not int or revision < 0:
            raise ValueError(f"a revision is a whole number from 0, not {revision!r}")
        held = self._latest.get(bot_id)
        if held is not None and held[0] >= revision:
            return False
        self._latest[bot_id] = (revision, value)
        return True

    def value_of(self, bot_id: str) -> T | None:
        held = self._latest.get(bot_id)
        return None if held is None else held[1]

    def revision_of(self, bot_id: str) -> int | None:
        held = self._latest.get(bot_id)
        return None if held is None else held[0]

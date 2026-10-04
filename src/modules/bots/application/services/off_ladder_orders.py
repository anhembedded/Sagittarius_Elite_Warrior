"""`EPIC-029E` — the run's orders no level holds whose fills still count (PR 325 review).

A fill arrives for an order the ladder does not hold in three cases, and only
two of them move the bot's inventory:

  · a market order the bot sent (an opening slice, an exit slice);
  · an order the bot took off the ladder (a cancel, an end while not
    running), whose fill may land just before the cancel did;
  · anything else: a late duplicate of a settled level's fill, or an order of
    an earlier run of the same bot. That changes nothing; the inventory is
    derived from the exchange again at the next stop, resume or restart.

Only the worker touches it. It lives for one run: a restart derives the
inventory from exchange history (ADR §3.3), so nothing here is persisted.
"""

from __future__ import annotations


class OffLadderOrders:
    """The ids whose fills are booked though no level holds them."""

    def __init__(self) -> None:
        self._ids: set[str] = set()

    def add(self, client_order_id: str | None) -> None:
        """Count `client_order_id`'s fills from now on (`None`: nothing sent)."""
        if client_order_id:
            self._ids.add(client_order_id)

    def __contains__(self, client_order_id: object) -> bool:
        return client_order_id in self._ids

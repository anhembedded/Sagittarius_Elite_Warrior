"""`EPIC-047E` (charter O5) — the honest line above the VPS tab: which host, what it holds, whether it is connected, how old the data is.

@details "nathan-warrior · Futures Mainnet key saved · connected · updated 2 s ago", or, with the link down, "nathan-warrior ·
disconnected, data as of 12:00:05 UTC" (decision record 2026-10-27, D5). The words are built from the host's published
facts and the link's status only; the tab never infers a state it was not told. The *exchange account* the epic's O5 names
(masked) is not published by the host — its facts file carries whether a venue has a key, never the key or any part of
it (`HostHeldFacts`, `EPIC-047B`) — so the line says which venues hold a key and no more. Publishing a masked tail is
the owner's decision, because it is derived from a secret.

@par Pure
A function of the world, the link status and `now`: no clock, no thread; a test hands it all three.
"""

from __future__ import annotations

from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_line import HostLine
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_world import (
    HostFile,
    HostFileState,
    HostWorld,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_status import (
    LinkState,
    LinkStatus,
)

_SEPARATOR = " · "
_NOTHING_PUBLISHED = "the host has published no facts yet"


def host_state_line(
    host: str, world: HostWorld, status: LinkStatus, now: datetime
) -> HostLine:
    if status.state is LinkState.CONNECTED:
        parts = [host, _keys_of(world), "connected", _updated(world, now)]
        return HostLine(
            _SEPARATOR.join(parts), world.held_file.state is HostFileState.LIVE
        )
    # The link's own words already say "disconnected, data as of ..." and what it is doing about it.
    return HostLine(_SEPARATOR.join([host, status.words, _keys_of(world)]), False)


def _keys_of(world: HostWorld) -> str:
    held = world.held
    if held is None:
        return _NOTHING_PUBLISHED
    saved = [key.venue.display_name for key in held.venue_keys if key.key_saved]
    return f"{', '.join(saved)} key saved" if saved else "no venue has an API key"


def _updated(world: HostWorld, now: datetime) -> str:
    """How current the host's facts are: their age when the desktop looked plus the time since, never the
    age of the last frame (a heartbeat or a bot event says the link lives, not that the facts are current)."""
    file = world.held_file
    if file.state is HostFileState.MISSING:
        return _NOTHING_PUBLISHED
    age = _age_of(file, now)
    if file.state is HostFileState.STALE:
        return f"host quiet: facts last written {age} s ago, it may have stopped"
    return f"facts updated {age} s ago"


def _age_of(file: HostFile, now: datetime) -> int:
    since_look = (
        0.0 if file.looked_at is None else (now - file.looked_at).total_seconds()
    )
    return max(0, int((file.age_s or 0.0) + since_look))

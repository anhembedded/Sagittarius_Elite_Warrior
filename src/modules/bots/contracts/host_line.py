"""`EPIC-047E` (charter O5) — the line above the VPS tab, as the screen draws it.

@details The shell builds the words from the host's published facts and the link's status (`shell/vps_link/host_state_line.py`);
the screen only draws them, once a second, so "updated 2 s ago" moves without an event. `ok` is true only while the link is up
**and** the host's facts are current: a quiet host or a cut link is drawn as a warning, never as good news.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HostLine:
    text: str
    ok: bool

"""The Welcome screen's one intent (ADR D13, SDD §4.6).

`StartRequested` is what the **Start** button raises. It is an *intent*, not a
navigation command, and the distinction is the whole reason the event exists:
the Welcome screen says "the user wants to begin", and *Main* — the entry
point — decides that beginning means the Trading surface. The day this app has
a real login, the button keeps raising exactly this and the decision moves
without the screen changing at all (HLD §4.6's own words about Start not being
"Login" yet).

Why an event and not a call: the shell owns this screen but cannot navigate. A
route change is `MainWindow`'s, which lives in the legacy tree the shell may
not import — and a navigation port with one caller would be a seam invented
ahead of the Engine's `NavigationService` (Phase 5), which is where it belongs.
The entry point already imports both halves, so the bus is the honest join.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StartRequested:
    """The user pressed Start on the Welcome screen."""

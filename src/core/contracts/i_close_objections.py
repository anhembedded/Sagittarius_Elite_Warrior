"""Why the app should not close yet, asked when the user closes the window.

`EPIC-029F` (ADR O4). A running bot keeps resting orders on the exchange, and
nothing watches its stop loss or take profit while the app is closed. The
window cannot know that: it names no module. So the inversion is the one
`ICliRegistry` makes — **the module declares, the shell asks** — and the
window only ever sees plain sentences.

An objection is asked at close time, never cached: whether a bot is running is
a fact about that moment.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ICloseObjection(ABC):
    """One context's reason, if it has one now, to keep the app open."""

    @abstractmethod
    def objection(self) -> str | None:
        """A sentence the user reads before closing, or `None` for none.

        Called on the UI thread when the window closes, so it reads state and
        returns; it never waits on a network call.
        """


class ICloseObjections(ABC):
    """The shell's collection of objections, in the order they registered."""

    @abstractmethod
    def register(self, objection: ICloseObjection) -> None:
        """Add `objection`; a module calls this once, from `boot()`."""

    @abstractmethod
    def reasons(self) -> tuple[str, ...]:
        """Every objection that has something to say now."""

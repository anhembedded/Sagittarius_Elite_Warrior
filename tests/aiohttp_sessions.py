"""`BUG-263` - read an `aiohttp` leak from the session itself.

A session is reported as unclosed when the garbage collector finds it, which a test cannot time;
this records every session opened while a test runs and answers which are still open.
"""

from __future__ import annotations

import aiohttp
import pytest


class Sessions:
    """Every `aiohttp` session opened while the test runs."""

    def __init__(self) -> None:
        self.opened: list[aiohttp.ClientSession] = []

    def unclosed(self) -> list[aiohttp.ClientSession]:
        return [session for session in self.opened if not session.closed]


def record_sessions(monkeypatch: pytest.MonkeyPatch) -> Sessions:
    seen = Sessions()
    original = aiohttp.ClientSession.__init__

    def recording(self: aiohttp.ClientSession, *args: object, **kwargs: object) -> None:
        original(self, *args, **kwargs)  # type: ignore[arg-type]
        seen.opened.append(self)

    monkeypatch.setattr(aiohttp.ClientSession, "__init__", recording)
    return seen

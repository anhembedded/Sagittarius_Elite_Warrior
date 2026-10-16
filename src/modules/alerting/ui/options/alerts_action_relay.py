"""Hands a worker's answer to the Alerts page on the UI thread (`EPIC-036D1`).

A `UiThreadRelay` whose `_deliver` calls the presenter. `close()` is final: an answer
reported after it is dropped, so a Send test still out when the Options dialog is
torn down never touches a view model that is gone.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.support.ui_kit.ui_thread_relay import UiThreadRelay


class AlertsActionRelay(UiThreadRelay):
    def __init__(self, on_answer: Callable[[tuple], None]) -> None:
        super().__init__()
        self._on_answer: Callable[[tuple], None] | None = on_answer

    def hand_over(self, answer: tuple) -> None:
        """Called on a worker thread; never touches a widget."""
        self._report(answer)

    def stop_delivering(self) -> None:
        self._on_answer = None

    def _deliver(self, payload: object) -> None:
        if self._on_answer is None:
            return
        if not isinstance(payload, tuple):
            raise TypeError(f"an action answers a tuple, not {type(payload).__name__}")
        self._on_answer(payload)

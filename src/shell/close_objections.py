"""`CloseObjections` — the shell's one list of reasons to keep the app open."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjection,
    ICloseObjections,
)

logger = logging.getLogger("App.Shell.CloseObjections")


class CloseObjections(ICloseObjections):
    """Asks each registered objection, in order, when the window closes.

    @details An objection that raises is logged and its context named as
    unchecked, rather than dropped: a broken check must not read as "nothing
    is running", and it must not trap the user in a window that cannot close
    either — the sentence goes to the same confirmation they can accept.
    """

    def __init__(self) -> None:
        self._objections: list[ICloseObjection] = []

    def register(self, objection: ICloseObjection) -> None:
        self._objections.append(objection)

    def reasons(self) -> tuple[str, ...]:
        found: list[str] = []
        for objection in self._objections:
            try:
                reason = objection.objection()
            except Exception:
                logger.exception("Close objection %s failed", type(objection).__name__)
                found.append(
                    f"{type(objection).__name__} could not check whether "
                    "anything is still running."
                )
                continue
            if reason:
                found.append(reason)
        return tuple(found)

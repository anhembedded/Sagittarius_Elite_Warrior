"""Tells the user that an indicator's saved parameters were ignored (`BOT-169`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
    failure_detail,
)


class SavedParamsFailures:
    """One message bar per script key, cleared when its parameters load again."""

    def __init__(self, notifier: INotifier, scope: str) -> None:
        self._notifier = notifier
        self._scope = scope
        self._ignored: set[str] = set()

    @staticmethod
    def cause(key: str) -> str:
        return f"indicators.saved_params.{key}"

    def ignored(self, key: str, exc: BaseException) -> None:
        """The saved parameters of `key` were refused: its defaults are used."""
        self._ignored.add(key)
        self._notifier.report_failure(
            FailureNotice(
                kind=FailureKind.BACKGROUND,
                cause=self.cause(key),
                headline=(
                    f"Saved parameters for {key} were ignored; the defaults are used."
                ),
                scope=self._scope,
                detail=failure_detail(exc),
            )
        )

    def accepted(self, key: str) -> None:
        """`key` was built from its saved parameters again."""
        if key in self._ignored:
            self._ignored.discard(key)
            self._notifier.clear_failure(self.cause(key))

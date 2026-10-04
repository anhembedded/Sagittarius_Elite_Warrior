"""`EPIC-029F` (ADR O4) — the shell asks every registered objection at close."""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjection,
)
from Sagittarius_Elite_Warrior.src.shell.close_objections import CloseObjections


class _Says(ICloseObjection):
    def __init__(self, reason: str | None) -> None:
        self._reason = reason

    def objection(self) -> str | None:
        return self._reason


class _Breaks(ICloseObjection):
    def objection(self) -> str | None:
        raise OSError("disk gone")


def test_only_objections_with_something_to_say_are_reasons() -> None:
    objections = CloseObjections()
    objections.register(_Says("bots running"))
    objections.register(_Says(None))
    objections.register(_Says("export unsaved"))

    assert objections.reasons() == ("bots running", "export unsaved")


def test_no_objection_registered_means_no_reason() -> None:
    assert CloseObjections().reasons() == ()


def test_a_broken_objection_is_named_unchecked_never_read_as_nothing_running(
    caplog: pytest.LogCaptureFixture,
) -> None:
    objections = CloseObjections()
    objections.register(_Breaks())
    objections.register(_Says("bots running"))

    with caplog.at_level(logging.ERROR, logger="App.Shell.CloseObjections"):
        reasons = objections.reasons()

    assert reasons[0].startswith("_Breaks could not check")
    assert reasons[1] == "bots running"
    assert "disk gone" in caplog.text

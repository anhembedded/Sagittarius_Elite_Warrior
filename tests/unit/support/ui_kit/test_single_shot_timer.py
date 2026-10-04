"""A burst of `start()` calls on a `single_shot_timer` is one call of its slot."""

from __future__ import annotations

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.support.ui_kit.single_shot_timer import (
    single_shot_timer,
)


def test_a_burst_of_starts_fires_the_slot_once(qtbot) -> None:
    owner = QObject()
    calls: list[int] = []
    timer = single_shot_timer(owner, 10, lambda: calls.append(1))

    assert not timer.isActive()
    for _ in range(3):
        timer.start()
    with qtbot.waitSignal(timer.timeout):
        pass

    assert calls == [1]
    assert timer.parent() is owner
    assert not timer.isActive()

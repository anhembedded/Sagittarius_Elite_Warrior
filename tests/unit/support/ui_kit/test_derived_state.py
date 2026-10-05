"""`EPIC-033D` — `DerivedState` re-reads its value on every notification."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.support.ui_kit.derived_state import DerivedState


class _Model(QObject):
    mode_changed = Signal()
    loading_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.mode = "IDLE"
        self.loading = False


def test_it_emits_what_read_answers_after_each_notification(qapp) -> None:
    model = _Model()
    state = DerivedState(model.mode_changed, lambda: model.mode == "IDLE", model)
    heard: list[bool] = []
    state.changed.connect(heard.append)

    model.mode = "LOCKED"
    model.mode_changed.emit()
    model.mode = "IDLE"
    model.mode_changed.emit()

    assert heard == [False, True]
    assert state.value is True


def test_a_second_notification_is_heard_too(qapp) -> None:
    model = _Model()
    state = DerivedState(
        model.mode_changed, lambda: model.mode == "IDLE" and not model.loading, model
    )
    state.listen(model.loading_changed)
    heard: list[bool] = []
    state.changed.connect(heard.append)

    model.loading = True
    model.loading_changed.emit()

    assert heard == [False]

"""`EPIC-019C` — `notifying_property()` factory."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.presentation.ui.common.qml_property import (
    notifying_property,
)


class _Widget(QObject):
    xChanged = Signal()  # noqa: N815 - Qt property-change signal naming
    symbolChanged = Signal()  # noqa: N815 - Qt property-change signal naming

    def __init__(self) -> None:
        super().__init__()
        self._x = 0
        self._symbol = "BTCUSDT"

    x = notifying_property("_x", int, xChanged)
    symbol = notifying_property(
        "_symbol",
        str,
        symbolChanged,
        normalize=lambda v: str(v or "").strip().upper(),
    )


def test_get_returns_backing_attribute() -> None:
    w = _Widget()
    assert w.x == 0


def test_set_updates_backing_attribute_and_emits_once() -> None:
    w = _Widget()
    received = []
    w.xChanged.connect(lambda: received.append(w.x))

    w.x = 5

    assert w.x == 5
    assert received == [5]


def test_set_same_value_does_not_emit() -> None:
    w = _Widget()
    received = []
    w.xChanged.connect(lambda: received.append(w.x))

    w.x = 0

    assert received == []


def test_normalize_applies_before_change_check() -> None:
    w = _Widget()
    received = []
    w.symbolChanged.connect(lambda: received.append(w.symbol))

    w.symbol = "ethusdt"

    assert w.symbol == "ETHUSDT"
    assert received == ["ETHUSDT"]


def test_normalize_falsy_result_is_ignored() -> None:
    w = _Widget()
    received = []
    w.symbolChanged.connect(lambda: received.append(w.symbol))

    w.symbol = "   "

    assert w.symbol == "BTCUSDT"
    assert received == []

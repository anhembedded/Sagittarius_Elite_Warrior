"""`BUG-118` regression: the cleanup this tier depends on must keep working.

The reported failure was not a wrong answer — it was the gate reaching 96% and
stalling there, twice, with nothing reported `FAILED`. The cause was cumulative:
UI tests leaked 20-30 MB each until two xdist workers held ~3.4 GB between them
and a 16 GB box with no swap started thrashing.

A test cannot assert "the gate finishes", and asserting a resident-memory number
would be a flaky test of the allocator rather than of this code. So it asserts
the **mechanism** instead, at the exact point where refcounting is not enough:
a reference cycle holding a `QWidget`.

Why that is the right subject. A first attempt asserted a plain
`weakref.ref(BackTestView())` dies after the release — and it passed **without
the fix**, because an acyclic widget is freed by refcounting the moment its last
reference goes. That test would have proven nothing, the same trap `BUG-013`
fell into (`bug-fix-rule.md` §4). A *cycle* is what the real views form — a view
holds its view-model, the view-model's signals hold the view's slots — and a
cycle survives until the cyclic collector runs.
"""

import gc
import weakref

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from Sagittarius_Elite_Warrior.tests.unit.presentation.qt_object_release import (
    release_qt_objects,
)


@pytest.fixture
def _no_automatic_gc():
    """Take the generational collector's timing out of the assertions.

    With it enabled the cycle below might be collected by an unrelated
    allocation crossing a threshold, so the test could pass for a reason that
    has nothing to do with `release_qt_objects()`.
    """
    gc.disable()
    yield
    gc.enable()


def test_a_reference_cycle_holding_a_widget_survives_refcounting(_no_automatic_gc):
    """The failure itself: dropping every reference is not enough.

    This is the half that must stay red if `gc.collect()` is ever taken out of
    `release_qt_objects()` — it pins down *why* the release is needed at all.
    """
    QApplication.instance() or QApplication([])

    holder: dict[str, object] = {}
    widget = QWidget()
    holder["widget"] = widget
    widget._holder = holder  # the cycle: dict -> widget -> dict
    reference = weakref.ref(widget)
    del widget, holder

    assert reference() is not None, (
        "a reference cycle was freed by refcounting alone — if this is ever "
        "true, re-derive BUG-118's root cause before trusting the fix"
    )


def test_release_qt_objects_collects_that_cycle(_no_automatic_gc):
    """The fix: one call returns what the test above proves is otherwise kept."""
    QApplication.instance() or QApplication([])

    holder: dict[str, object] = {}
    widget = QWidget()
    holder["widget"] = widget
    widget._holder = holder
    reference = weakref.ref(widget)
    del widget, holder

    release_qt_objects()

    assert reference() is None, (
        "release_qt_objects() no longer frees a cycle holding a QWidget — the "
        "BUG-118 leak is back, and the gate will stall again once enough UI "
        "tests run in one worker"
    )


def test_release_qt_objects_is_safe_to_call_twice():
    """The autouse fixture runs it after every test, including tests that
    created nothing and tests that already called it themselves."""
    release_qt_objects()
    release_qt_objects()

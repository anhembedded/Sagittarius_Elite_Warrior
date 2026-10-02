"""`BUG-140` regression: a worker thread never runs the cyclic garbage collector.

@details CPython runs a generational collection on whichever thread happens to
allocate past the threshold. In this suite that was a `concurrent.futures`
pool worker (`runner.py:268 feed`) and, on PR 311, xdist's execnet receiver
thread. The collection finalized Qt wrappers of an earlier test's widget
cycles off the main thread while the main thread was inside Qt
(`table_model.py:133 columnCount`), and the process died with
`Segmentation fault`.

The root `tests/conftest.py` turns automatic collection off for the whole
process and collects on the main thread after every test, which is the policy
`app_bootstrapper.build()` installs for the app (`main_thread_collection.py`).
These tests pin the policy at the point it matters: garbage made of a
reference cycle, a burst of allocation on a worker thread, and the thread its
finalizer runs on.
"""

from __future__ import annotations

import gc
import threading

import pytest
import shiboken6
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.main_thread_collection import (
    collect_due_generations,
)
from Sagittarius_Elite_Warrior.tests.conftest import release_finished_test_objects

#: Far past CPython's first threshold (700) and its tenfold second one, so an
#: enabled collector would run every generation the cycle could be in.
_ALLOCATIONS = 200_000


class _Finalized:
    """One half of a reference cycle that records where it was finalized."""

    def __init__(self, threads: list[str]) -> None:
        self.threads = threads
        self.partner: object = None

    def __del__(self) -> None:
        self.threads.append(threading.current_thread().name)


def _make_cyclic_garbage(threads: list[str]) -> None:
    first = _Finalized(threads)
    second = _Finalized(threads)
    first.partner = second
    second.partner = first


def _allocate_on_a_worker_thread() -> list[list[object]]:
    """Returns what it allocated: a freed object lowers CPython's count
    again, and the caller's collection would then not be due."""
    kept: list[list[object]] = []

    def allocate() -> None:
        kept.extend([] for _ in range(_ALLOCATIONS))

    worker = threading.Thread(target=allocate, name="allocating-worker")
    worker.start()
    worker.join()
    return kept


def test_a_worker_thread_allocation_burst_collects_nothing() -> None:
    finalized_on: list[str] = []
    _make_cyclic_garbage(finalized_on)

    allocated = _allocate_on_a_worker_thread()

    assert allocated
    assert "allocating-worker" not in finalized_on, (
        "the cyclic collector ran on a worker thread: Qt objects in a cycle "
        "would be finalized off the main thread (BUG-140)"
    )


def test_the_main_thread_collects_what_the_worker_left() -> None:
    finalized_on: list[str] = []
    _make_cyclic_garbage(finalized_on)
    allocated = _allocate_on_a_worker_thread()

    collect_due_generations()
    del allocated

    assert finalized_on == [threading.main_thread().name] * 2


def test_collecting_off_the_main_thread_is_refused() -> None:
    errors: list[BaseException] = []

    def collect() -> None:
        try:
            collect_due_generations()
        except RuntimeError as error:
            errors.append(error)

    worker = threading.Thread(target=collect)
    worker.start()
    worker.join()

    assert len(errors) == 1


def test_automatic_collection_stays_off_for_every_test(
    request: pytest.FixtureRequest,
) -> None:
    """Remove the fixture's `autouse=True`, or the policy, and this fails."""
    assert "_release_finished_test_objects" in request.fixturenames
    assert not gc.isenabled()


class _DeletesLaterWhenFinalized:
    """One half of a cycle whose finalizer queues a widget's deletion, as a
    collected view's wrapper does for the Qt objects it owned."""

    def __init__(self, widget: QWidget) -> None:
        self.widget = widget
        self.partner: object = None

    def __del__(self) -> None:
        self.widget.deleteLater()


def test_a_finished_tests_cycles_are_destroyed_by_its_own_release(qapp) -> None:
    """Collect, then flush: in the other order the deletion the collection
    queues stays pending into the next test. Swap the two lines of
    `release_finished_test_objects()` and this fails."""
    widget = QWidget()
    first = _DeletesLaterWhenFinalized(widget)
    first.partner = _DeletesLaterWhenFinalized(widget)
    first.partner.partner = first
    del first
    # Make the youngest generation due, as a test's own allocation does.
    padding = [[] for _ in range(gc.get_threshold()[0] + 1)]

    release_finished_test_objects()

    assert not shiboken6.isValid(widget)
    del padding

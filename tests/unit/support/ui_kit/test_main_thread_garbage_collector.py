"""`BUG-140` — the app's timer collects cyclic garbage on the main thread.

The policy itself is pinned by `tests/unit/test_garbage_is_collected_on_the_main_thread.py`;
this file pins the app's scheduler for it. Its wiring into `build()` is pinned
by `tests/sanity/test_self_check_process.py`, against the real process's log.
"""

from __future__ import annotations

import gc
import threading

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.support.ui_kit.main_thread_garbage_collector import (
    MainThreadGarbageCollector,
)


class _Finalized:
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


def test_the_timer_collects_cyclic_garbage_on_the_main_thread(qtbot) -> None:
    owner = QObject()
    collector = MainThreadGarbageCollector(owner)
    collector.start()
    finalized_on: list[str] = []
    _make_cyclic_garbage(finalized_on)
    # Push the youngest generation past its threshold, as the app's own
    # allocation does between two ticks.
    padding = [[] for _ in range(gc.get_threshold()[0] + 1)]

    qtbot.waitUntil(lambda: bool(finalized_on), timeout=2000)

    assert not gc.isenabled()
    assert finalized_on == [threading.main_thread().name] * 2
    del padding
    owner.deleteLater()

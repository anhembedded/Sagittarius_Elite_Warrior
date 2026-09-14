"""Give a finished test's Qt objects back to the operating system (`BUG-118`).

One function, in its own file rather than inside `conftest.py`, because the
fixture that schedules it and the mechanism it performs are two different things
(`architecture-rule.md` §5): the fixture decides *when*, this decides *what*,
and `test_qt_object_release.py` can only assert the *what* if it can call it
without pytest arranging a fixture first.

**Why refcounting is not enough here.** A Qt view is a graph, not a tree: a view
holds its view-model, the view-model's signals hold the view's slots, and a
presenter sits on both sides. That is a reference **cycle**, and CPython cannot
free a cycle by refcounting — only the cyclic collector can, and it runs on its
own generational schedule. Between collections the cycles pile up, each pinning
a `QQuickWidget` and its QML engine, ~20-30 MB at a time. Measured: one
164-test file peaked at **2.86 GB** without this call and **258 MB** with it.

That is also why the order below is not interchangeable. `gc.collect()` must run
**first**: breaking the cycles is what drops the Python wrappers, which is what
queues the underlying C++ deletions. Draining first would drain an empty queue
and then fill it.
"""

import gc

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


def release_qt_objects() -> None:
    """Break reference cycles, then let Qt actually run the deletions.

    Safe to call with no `QApplication` (a pure-logic test in this tier never
    creates one), and safe to call twice.
    """
    # 1. Break the cycles. Without this the wrappers survive, so nothing below
    #    has anything to delete.
    gc.collect()

    # 2. Run the deletions now. `deleteLater()` only *queues*; unless something
    #    pumps, the queue is carried into the next test — which is the other
    #    half of this problem and, as `BUG-056` records for the integration
    #    tier, dangerous if a worker thread is running by then.
    app = QApplication.instance()
    if app is not None:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()

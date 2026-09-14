"""Every unit UI test gives its Qt objects back when it finishes (`BUG-118`).

Scoped to this directory on purpose. This is the tier that constructs real views
without `qtbot` — `view = BackTestView()` in a fixture, and nothing else — so
nobody schedules the deletions and nobody pumps the event loop. The integration
tier has its own, more careful teardown that also owns engine and thread
lifetimes (`BUG-056`); it must not have a second one pumping underneath it.

What the release actually does, and why refcounting cannot do it, is in
`qt_object_release.py`.
"""

import pytest
from Sagittarius_Elite_Warrior.tests.unit.presentation.qt_object_release import (
    release_qt_objects,
)


@pytest.fixture(autouse=True)
def _release_qt_objects_after_each_test():
    """Autouse: no test opts in, and none can forget."""
    yield
    release_qt_objects()

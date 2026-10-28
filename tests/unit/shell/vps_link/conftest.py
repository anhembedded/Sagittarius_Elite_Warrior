"""`EPIC-047E` - the VPS tab's tests share one running world per test."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import VpsTabWorld


@pytest.fixture
def tab() -> Iterator[VpsTabWorld]:
    built = VpsTabWorld().start()
    yield built
    built.stop()

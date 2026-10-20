"""The `world` fixture of the `sew-key` script tests (`BOT-200`)."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.scripts.sew_key_world import World


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)

"""The fixtures of the `sew-key` (`BOT-200`) and `sew-install` / `sew-update` (`BOT-204`) script tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.scripts.deploy_world import DeployWorld
from Sagittarius_Elite_Warrior.tests.unit.scripts.sew_key_world import World


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


@pytest.fixture
def deploy(tmp_path: Path) -> DeployWorld:
    return DeployWorld(tmp_path)

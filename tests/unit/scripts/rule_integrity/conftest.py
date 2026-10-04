"""The `make_repo` fixture: a fake repository on `tmp_path`."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.scripts.rule_integrity.fake_repo import (
    MakeRepo,
    write_repo,
)


@pytest.fixture
def make_repo(tmp_path: Path) -> MakeRepo:
    return lambda files: write_repo(tmp_path, files)

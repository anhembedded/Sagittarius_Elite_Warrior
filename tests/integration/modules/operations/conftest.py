"""Fixtures for the operations module's integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A data root of its own, which `create_app()` and the stores resolve through the environment."""
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
    return tmp_path

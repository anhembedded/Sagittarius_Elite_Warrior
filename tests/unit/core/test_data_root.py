"""`EPIC-030M` — `data_root()`: the repository root unless `SEW_DATA_ROOT` moves it."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import (
    DATA_ROOT_ENV,
    data_root,
    data_root_override,
    repo_root,
)


def test_unset_is_the_repository_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)

    assert data_root_override() is None
    assert data_root() == repo_root()
    assert (data_root() / "pyproject.toml").is_file()


def test_empty_is_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, "")

    assert data_root_override() is None
    assert data_root() == repo_root()


def test_set_redirects_and_says_so(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))

    with caplog.at_level(logging.INFO, logger="App.DataRoot"):
        resolved = data_root()

    assert resolved == tmp_path
    assert data_root_override() == tmp_path
    assert any(
        "[data-root]" in record.getMessage() and DATA_ROOT_ENV in record.getMessage()
        for record in caplog.records
    )

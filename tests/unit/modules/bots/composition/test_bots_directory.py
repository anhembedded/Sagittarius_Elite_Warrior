"""`EPIC-030M` — the bots store lives under the data root unless `bots.state_dir` says otherwise."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV, repo_root
from Sagittarius_Elite_Warrior.src.modules.bots.composition.state_bindings import (
    bots_directory,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig


def test_unset_is_state_bots_under_the_repository_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)

    assert bots_directory(DictConfig({})) == repo_root() / "state" / "bots"


def test_set_moves_it_under_the_data_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))

    assert bots_directory(DictConfig({})) == tmp_path / "state" / "bots"


def test_the_configuration_key_still_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path / "ignored"))
    configured = tmp_path / "chosen"

    directory = bots_directory(
        DictConfig({ConfigKeys.BOTS_STATE_DIR.value: str(configured)})
    )

    assert directory == configured

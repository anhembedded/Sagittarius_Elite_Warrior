"""`EPIC-030M` — the shard directory's precedence: an explicit choice, then
`SEW_DATA_ROOT`, then the configured relative path, then `<cwd>/database`."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseConfig,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.database_directory import (
    database_directory,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.interfaces.i_config import IConfig

_CWD = os.path.abspath("/work")
_SHIPPED_RELATIVE = "Sagittarius_Elite_Warrior/database"


def test_unset_override_keeps_the_configured_relative_value_verbatim() -> None:
    assert database_directory(_SHIPPED_RELATIVE, None, _CWD) == _SHIPPED_RELATIVE


def test_unset_override_and_no_configuration_is_cwd_database() -> None:
    assert database_directory(None, None, _CWD) == os.path.join(_CWD, "database")


@pytest.mark.parametrize("configured", [_SHIPPED_RELATIVE, None])
def test_the_override_wins_over_a_relative_or_missing_value(
    configured: str | None, tmp_path: Path
) -> None:
    assert database_directory(configured, tmp_path, _CWD) == str(tmp_path / "database")


@pytest.mark.parametrize("configured", [":memory:", os.path.abspath("/data/shards")])
def test_an_explicit_choice_wins_over_the_override(
    configured: str, tmp_path: Path
) -> None:
    assert database_directory(configured, tmp_path, _CWD) == configured


def test_the_binding_applies_the_override_to_the_shipped_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Against the real binding: the shipped relative `database.dir` must not
    win over `SEW_DATA_ROOT`, or a test boot writes into the checkout."""
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
    container = StdLibContainer()
    container.singleton(
        IConfig, DictConfig({ConfigKeys.DATABASE_DIR.value: _SHIPPED_RELATIVE})
    )
    bind_adapters(container)

    assert container.resolve(DatabaseConfig).db_dir == str(tmp_path / "database")

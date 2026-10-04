"""`resolve_default_exports_dir` — where the export dialog opens when no
directory is configured (`BOT-112D`), and that a test run's `SEW_DATA_ROOT`
keeps that fallback out of the checkout (`EPIC-030M`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.logic.export_paths import (
    resolve_default_exports_dir,
)


def test_falls_back_to_cwd_exports_when_no_data_root_is_set(tmp_path, monkeypatch):
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)
    monkeypatch.chdir(tmp_path)

    exports_dir = resolve_default_exports_dir(None)

    assert exports_dir == str(tmp_path / "exports")
    assert (tmp_path / "exports").is_dir()


def test_falls_back_under_the_data_root_when_set(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_root = tmp_path / "data_root"
    monkeypatch.setenv(DATA_ROOT_ENV, str(data_root))

    exports_dir = resolve_default_exports_dir(None)

    assert exports_dir == str(data_root / "exports")
    assert (data_root / "exports").is_dir()
    assert not (tmp_path / "exports").exists()


def test_a_configured_directory_wins_over_the_data_root(tmp_path, monkeypatch):
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path / "data_root"))
    configured = tmp_path / "custom_exports"

    exports_dir = resolve_default_exports_dir(str(configured))

    assert exports_dir == str(configured)
    assert configured.is_dir()

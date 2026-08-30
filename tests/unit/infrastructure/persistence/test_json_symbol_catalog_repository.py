"""Unit tests for JsonSymbolCatalogRepository."""

from __future__ import annotations

import json
from pathlib import Path

from Sagittarius_Elite_Warrior.src.infrastructure.persistence.json_symbol_catalog_repository import (
    JsonSymbolCatalogRepository,
)


def test_get_symbols_returns_empty_when_file_not_found(tmp_path: Path) -> None:
    non_existent = tmp_path / "missing.json"
    repo = JsonSymbolCatalogRepository(non_existent)

    assert repo.get_symbols() == []


def test_get_symbols_reads_valid_json_file(tmp_path: Path) -> None:
    file_path = tmp_path / "symbols.json"
    file_path.write_text(json.dumps(["btcusdt", "ethusdt"]), encoding="utf-8")
    repo = JsonSymbolCatalogRepository(file_path)

    assert repo.get_symbols() == ["BTCUSDT", "ETHUSDT"]


def test_get_symbols_handles_corrupted_json_gracefully(tmp_path: Path) -> None:
    file_path = tmp_path / "corrupted.json"
    file_path.write_text("invalid json content", encoding="utf-8")
    repo = JsonSymbolCatalogRepository(file_path)

    assert repo.get_symbols() == []


def test_get_symbols_handles_non_list_json_gracefully(tmp_path: Path) -> None:
    file_path = tmp_path / "dict.json"
    file_path.write_text(json.dumps({"symbol": "BTCUSDT"}), encoding="utf-8")
    repo = JsonSymbolCatalogRepository(file_path)

    assert repo.get_symbols() == []


def test_save_symbols_writes_cleaned_sorted_uppercase_list(tmp_path: Path) -> None:
    file_path = tmp_path / "saved.json"
    repo = JsonSymbolCatalogRepository(file_path)

    repo.save_symbols(["ethusdt", "BTCUSDT", "ethusdt", "  solusdt  "])

    assert file_path.is_file()
    saved = json.loads(file_path.read_text(encoding="utf-8"))
    assert saved == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

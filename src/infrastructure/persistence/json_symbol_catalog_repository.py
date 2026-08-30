"""JSON file implementation of ISymbolCatalogRepository."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from Sagittarius_Elite_Warrior.src.application.ports.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
)

logger = logging.getLogger("App.Persistence")


class JsonSymbolCatalogRepository(ISymbolCatalogRepository):
    """Stores and retrieves tradeable symbols from a local JSON file."""

    def __init__(self, file_path: str | Path | None = None) -> None:
        if file_path is None:
            # Default location: src/config/tradeable_symbols.json
            self._file_path = (
                Path(__file__).resolve().parent.parent.parent
                / "config"
                / "tradeable_symbols.json"
            )
        else:
            self._file_path = Path(file_path).resolve()

    def get_symbols(self) -> list[str]:
        """Reads cached symbols from disk."""
        if not self._file_path.is_file():
            logger.debug(
                "Symbol catalog file not found at %s. Returning empty list.",
                self._file_path,
            )
            return []

        try:
            with open(self._file_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [
                    str(s).strip().upper()
                    for s in data
                    if isinstance(s, str) and s.strip()
                ]
            logger.warning(
                "Invalid symbol catalog format in %s (expected list).",
                self._file_path,
            )
            return []
        except Exception:
            logger.exception("Failed to read symbol catalog from %s", self._file_path)
            return []

    def save_symbols(self, symbols: list[str]) -> None:
        """Saves tradeable symbols to disk."""
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            cleaned = sorted(
                {
                    str(s).strip().upper()
                    for s in symbols
                    if isinstance(s, str) and s.strip()
                }
            )
            temp_path = self._file_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(cleaned, f, indent=2)
            temp_path.replace(self._file_path)
            logger.info(
                "Saved %d tradeable symbols to %s", len(cleaned), self._file_path
            )
        except Exception:
            logger.exception("Failed to save symbol catalog to %s", self._file_path)

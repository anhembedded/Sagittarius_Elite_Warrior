"""JSON file implementation of ISymbolCatalogRepository."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog_repository import (
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

    def _path_for(self, market: MarketType) -> Path:
        """`EPIC-027D` — one file per market. Spot keeps the original file
        name, which is what every catalog saved before a market existed holds
        (the only catalog this app ever fetched was Spot's)."""
        if market is MarketType.SPOT:
            return self._file_path
        return self._file_path.with_name(
            f"{self._file_path.stem}_{market.value}{self._file_path.suffix}"
        )

    def get_symbols(self, market: MarketType) -> list[str]:
        """Reads one market's cached symbols from disk."""
        path = self._path_for(market)
        if not path.is_file():
            logger.debug(
                "Symbol catalog file not found at %s. Returning empty list.", path
            )
            return []

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [
                    str(s).strip().upper()
                    for s in data
                    if isinstance(s, str) and s.strip()
                ]
            logger.warning("Invalid symbol catalog format in %s (expected list).", path)
            return []
        except Exception:
            logger.exception("Failed to read symbol catalog from %s", path)
            return []

    def save_symbols(self, market: MarketType, symbols: list[str]) -> None:
        """Saves one market's tradeable symbols to disk."""
        path = self._path_for(market)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            cleaned = sorted(
                {
                    str(s).strip().upper()
                    for s in symbols
                    if isinstance(s, str) and s.strip()
                }
            )
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(cleaned, f, indent=2)
            temp_path.replace(path)
            logger.info("Saved %d tradeable symbols to %s", len(cleaned), path)
        except Exception:
            logger.exception("Failed to save symbol catalog to %s", path)

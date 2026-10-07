"""Gives the candles stored before `BUG-172` the source they came from, once.

@details Before `BUG-172` the store held one series per market, fetched from
whatever `exchange.market_data_venue` said when it was synced, with no label. Now
each venue has its own store, so those rows must be given one without ever turning
a testnet candle into a mainnet one: the rows belong to the venue the setting names
**when this runs**, which is the only evidence the app has of where they came from.

- The setting names a venue: the legacy shards move into that venue's store
  (`venue_directory`); for the mainnet they stay where they are.
- The setting is missing or names no venue: the provenance is unknown, so the
  shards are **quarantined** under `QUARANTINE_DIRECTORY` — unlabelled, never read
  by any venue — and the history syncs again. Nothing is guessed.

Runs once: `MARKER` records the outcome, and a store with nothing to label gets
one too, so rows written afterwards are never taken for legacy ones. Moves files,
never deletes data, and refuses to overwrite one that is already there.
"""

from __future__ import annotations

import logging
import shutil
from enum import Enum
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.venue_directory import (
    venue_directory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.extensions.persistence.sqlite_shard_manager import IN_MEMORY

logger = logging.getLogger("App.Database")

#: Written in the configured directory when the legacy store was labelled.
MARKER = ".market_data_source"
#: Where legacy shards of unknown origin wait; no venue's store is this directory.
QUARANTINE_DIRECTORY = "legacy_unlabelled"
_SHARD_FILES = ("*.db", "*.db-wal", "*.db-shm")


class LegacyStoreOutcome(Enum):
    """What `label_legacy_store` did."""

    ALREADY_LABELLED = "already_labelled"
    NOTHING_TO_LABEL = "nothing_to_label"
    LABELLED = "labelled"
    QUARANTINED = "quarantined"


def label_legacy_store(base: str, configured: object) -> LegacyStoreOutcome:
    """@brief Labels the shards directly in `base` with the venue `configured`
    (the raw `exchange.market_data_venue`) names, or quarantines them.

    @raise FileExistsError a destination file exists already; nothing was moved
    and no marker was written, so the next start tries again.
    """
    directory = Path(base)
    if base == IN_MEMORY or (directory / MARKER).exists():
        return LegacyStoreOutcome.ALREADY_LABELLED
    legacy = [path for pattern in _SHARD_FILES for path in directory.glob(pattern)]
    if not legacy:
        _record(directory, "nothing to label")
        return LegacyStoreOutcome.NOTHING_TO_LABEL
    venue = _venue_named(configured)
    if venue is None:
        _move(legacy, directory / QUARANTINE_DIRECTORY)
        _record(directory, f"quarantined: setting {configured!r} names no venue")
        logger.warning(
            "Stored candles of unknown origin (exchange.market_data_venue is %r) "
            "were set aside in %s; they are served to no venue and will sync again.",
            configured,
            directory / QUARANTINE_DIRECTORY,
        )
        return LegacyStoreOutcome.QUARANTINED
    target = Path(venue_directory(base, venue))
    if target != directory:
        _move(legacy, target)
    _record(directory, f"labelled: {venue.value}")
    logger.info(
        "Stored candles from before the market-data source was kept are labelled "
        "%s, the venue exchange.market_data_venue names (%d files).",
        venue.value,
        len(legacy),
    )
    return LegacyStoreOutcome.LABELLED


def _venue_named(configured: object) -> MarketDataVenue | None:
    try:
        return MarketDataVenue(configured)
    except ValueError:
        return None


def _move(files: list[Path], target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    clashes = [path.name for path in files if (target / path.name).exists()]
    if clashes:
        raise FileExistsError(f"{target} already holds {sorted(clashes)}")
    for path in files:
        shutil.move(str(path), str(target / path.name))


def _record(directory: Path, outcome: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MARKER).write_text(outcome + "\n", encoding="utf-8")

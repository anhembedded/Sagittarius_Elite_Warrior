"""Gives the candles stored before `BUG-172` the source they came from, once.

@details Before `BUG-172` the store held one series per market, fetched from
whatever `exchange.market_data_venue` said when it was synced, with no label. Now
each venue has its own store, so those rows must be given one without ever turning
a testnet candle into a mainnet one: the rows belong to the venue the setting names
**when this runs**, which is the only evidence the app has of where they came from.

- The setting names a venue: the legacy shards move into that venue's store
  (`venue_directory`); for the mainnet they stay where they are.
- The setting is **absent**: the app read its default, `mainnet_public` (what
  `resolve_market_data_venue` did before), so that is what the rows are.
- The setting is present but names no venue (`"mainnet"`, `5`, `""`): the provenance
  is unknown, so the shards are **quarantined** under `QUARANTINE_DIRECTORY` —
  unlabelled, never read by any venue — and the history syncs again. Nothing is
  guessed. Quarantine is also where shards go when their venue's store already
  holds a file of the same name: boot goes on, and nothing is overwritten.

Runs once: `MARKER` records the outcome, and a store with nothing to label gets
one too, so rows written afterwards are never taken for legacy ones. Moves only
files named like a shard as an earlier build wrote one (a bare upper-case symbol or
`<market>_<symbol>`, so a sibling `bots.db` stays), never deletes data, and never overwrites a file that is
already there. A move that fails for any other reason (permissions, a full disk)
stops boot with the error logged: leaving the shards in place would serve them as
the mainnet's whatever the setting says.
"""

from __future__ import annotations

import logging
import re
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
#: A shard file as an earlier build wrote it — a bare upper-case symbol
#: (`BTCUSDT`, before `EPIC-027A`) or `<market>_<symbol>` — and its SQLite sidecars.
#: Anything else in the directory (`bots.db`, a user's own `.db`, a note) is not ours
#: to move.
_SHARD_FILE = re.compile(
    r"^((spot|futures_usd_m|futures_coin_m)_)?[A-Z0-9]+\.db(-wal|-shm)?$"
)


class LegacyStoreOutcome(Enum):
    """What `label_legacy_store` did."""

    ALREADY_LABELLED = "already_labelled"
    NOTHING_TO_LABEL = "nothing_to_label"
    LABELLED = "labelled"
    QUARANTINED = "quarantined"


def label_legacy_store(base: str, configured: object) -> LegacyStoreOutcome:
    """@brief Labels the shards directly in `base` with the venue `configured`
    (the raw `exchange.market_data_venue`) names, or quarantines them.

    """
    directory = Path(base)
    if base == IN_MEMORY or (directory / MARKER).exists():
        return LegacyStoreOutcome.ALREADY_LABELLED
    legacy = sorted(
        path
        for path in (directory.iterdir() if directory.is_dir() else ())
        if path.is_file() and _SHARD_FILE.match(path.name)
    )
    if not legacy:
        _record(directory, "nothing to label")
        return LegacyStoreOutcome.NOTHING_TO_LABEL
    venue = (
        MarketDataVenue.MAINNET_PUBLIC
        if configured is None
        else _venue_named(configured)
    )
    if venue is None:
        return _quarantine(directory, legacy, f"setting {configured!r} names no venue")
    target = Path(venue_directory(base, venue))
    if target != directory:
        try:
            _move(legacy, target)
        except FileExistsError as clash:
            return _quarantine(directory, legacy, str(clash))
    _record(directory, f"labelled: {venue.value}")
    logger.info(
        "Stored candles from before the market-data source was kept are labelled "
        "%s, the venue exchange.market_data_venue names (%d files).",
        venue.value,
        len(legacy),
    )
    return LegacyStoreOutcome.LABELLED


def _quarantine(directory: Path, files: list[Path], why: str) -> LegacyStoreOutcome:
    target = directory / QUARANTINE_DIRECTORY
    suffix = 1
    while target.exists():
        suffix += 1
        target = directory / f"{QUARANTINE_DIRECTORY}-{suffix}"
    _move(files, target)
    _record(directory, f"quarantined: {why}")
    logger.warning(
        "Stored candles of unknown origin (%s) were set aside in %s; they are "
        "served to no venue and will sync again.",
        why,
        target,
    )
    return LegacyStoreOutcome.QUARANTINED


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
        try:
            shutil.move(str(path), str(target / path.name))
        except OSError as failure:
            # Fail closed: shards left in the configured directory would be served
            # as the mainnet's whatever the setting says, so the app does not start.
            logger.error(
                "Could not move stored candles %s to %s (%s); refusing to start "
                "rather than serve candles of unknown origin.",
                path,
                target,
                failure,
            )
            raise


def _record(directory: Path, outcome: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MARKER).write_text(outcome + "\n", encoding="utf-8")

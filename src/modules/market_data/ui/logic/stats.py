"""`BOT-144` — the Storage Vault stat tiles' values, extracted out of
`DataManagementPresenter` (part of bringing that file under the
`architecture-rule.md` §5.4 400-line ceiling).

@details A pure `Path | str | None -> int | None` computation with no `self`
dependency beyond the already-resolved config value, mirroring
`export_paths.py`'s own reasoning for living here rather than on the
Presenter.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def database_size_bytes(raw_dir: object) -> int | None:
    """Sums on-disk SQLite files under `raw_dir`, or `None` if it is unset,
    not a directory, unreadable or holds nothing: the size is then unknown,
    and the read-out writes it blank (`AppValueFormatter`'s `BYTES_KEY`)."""
    if not isinstance(raw_dir, (str, Path)) or not str(raw_dir).strip():
        return None

    try:
        directory = Path(raw_dir)
        if not directory.is_dir():
            return None
        total_bytes = sum(
            path.stat().st_size for path in directory.glob("*.db*") if path.is_file()
        )
    except OSError:
        return None

    return total_bytes or None


def stored_records(candle_counts: Iterable[int]) -> int | None:
    """Every shard's candles, summed, or `None` before a scan has counted any."""
    return sum(candle_counts) or None

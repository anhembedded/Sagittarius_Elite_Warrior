"""`BOT-144` — the Storage Vault size stat tile's text, extracted out of
`DataManagementPresenter` (part of bringing that file under the
`architecture-rule.md` §5.4 400-line ceiling).

@details A pure `Path | str | None -> str` computation with no `self`
dependency beyond the already-resolved config value, mirroring
`export_paths.py`'s own reasoning for living here rather than on the
Presenter.
"""

from __future__ import annotations

from pathlib import Path

_UNKNOWN_STAT = "—"
_BYTES_PER_MB = 1024 * 1024


def database_size_text(raw_dir: object) -> str:
    """Sums on-disk SQLite files under `raw_dir`, or `_UNKNOWN_STAT` if it
    is unset, not a directory, or unreadable."""
    if not isinstance(raw_dir, (str, Path)) or not str(raw_dir).strip():
        return _UNKNOWN_STAT

    try:
        directory = Path(raw_dir)
        if not directory.is_dir():
            return _UNKNOWN_STAT
        total_bytes = sum(
            path.stat().st_size for path in directory.glob("*.db*") if path.is_file()
        )
    except OSError:
        return _UNKNOWN_STAT

    if not total_bytes:
        return _UNKNOWN_STAT
    return f"{total_bytes / _BYTES_PER_MB:.2f} MB"

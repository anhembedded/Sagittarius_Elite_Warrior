"""`BOT-112D` — where the export file dialog opens and what it suggests.

@details Mirrors `backtesting/ui/logic/report_export.py`'s
`resolve_default_reports_dir()`/`suggest_report_filename()` shape: a
presenter-owned `QFileDialog` needs a starting directory and a suggested
name, and both are pure functions of config + the export request so they
can be tested without a `QFileDialog` in sight.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.export_file_format import (
    ExportFileFormat,
)

DEFAULT_EXPORTS_DIR_NAME = "exports"

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def resolve_default_exports_dir(configured_dir: str | None) -> str:
    """`configured_dir` is `IConfig.get(ConfigKeys.MARKET_DATA_EXPORTS_DIR.value)`
    — falsy (unset) falls back to `<cwd>/exports`, created if missing so the
    file dialog always opens somewhere real."""
    exports_dir = configured_dir or os.path.join(os.getcwd(), DEFAULT_EXPORTS_DIR_NAME)
    os.makedirs(exports_dir, exist_ok=True)
    return exports_dir


def suggest_export_filename(
    symbol: str, interval: str, file_format: ExportFileFormat, created_at: datetime
) -> str:
    """e.g. `BTCUSDT_1h_20260923_1432.csv` — sanitized for the filesystem
    rather than assumed safe (symbol/interval are app data, not something
    this function should trust blindly)."""
    stamp = created_at.strftime("%Y%m%d_%H%M")
    raw = f"{symbol}_{interval}_{stamp}"
    safe = _UNSAFE_FILENAME_CHARS.sub("_", raw)
    return f"{safe}.{file_format.value}"


def export_file_filter(file_format: ExportFileFormat) -> str:
    """The `QFileDialog.getSaveFileName()` filter string for one format."""
    labels = {
        ExportFileFormat.CSV: "CSV Files (*.csv)",
        ExportFileFormat.JSON: "JSON Files (*.json)",
        ExportFileFormat.PARQUET: "Parquet Files (*.parquet)",
    }
    return labels[file_format]

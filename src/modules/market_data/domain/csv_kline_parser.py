"""Parsing an external candle CSV into `MarketData` — the read half of
`BOT-112D`'s offline import.

Domain, not infrastructure: this only turns already-read text into the
domain's own value object, no file handle, no database — the same reasoning
`candle_time.py` gives for living here. `import_market_data/handler.py` owns
opening the file and calling `IMarketDataRepository.save_klines()`.

@par Which CSV dialects this covers
No single fixed header, because none of the three tools this task names
(Binance's own data-export, TradingView's chart export, MetaTrader's export)
agree on one: Binance writes `open_time,open,high,low,close,volume,close_time,
quote_asset_volume,number_of_trades,taker_buy_base_asset_volume,
taker_buy_quote_asset_volume`, TradingView writes `time,open,high,low,close,
Volume` (unix seconds), MetaTrader writes `Date,Time,Open,High,Low,Close,
Volume` — dot-separated `Date` (`2024.01.15`), joined with the separate
`Time` column when both are present — or `Date` alone already carrying a
full timestamp (a bare single-column export some tools produce instead).
Rather than one parser per named tool — three near-duplicates that drift
out of sync the moment a tool changes its export format — this reads the
header once, maps each column by a case-insensitive alias table, and
requires only what no kline can be built without: an open time and OHLC.
Everything Binance-specific
(`quote_asset_volume`, `number_of_trades`, the two taker-buy columns)
defaults to `0`/`0.0` when the file does not carry it — the same "not every
source has this" convention `Trade.leverage`/`.mae_percent` already use.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from typing import cast

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

#: One entry per `MarketData` field this parser can fill from a column,
#: value = every header spelling (lowercased) accepted for it. Checked in
#: this order, first match wins — `_ALIASES["open_time"]` covers both a
#: dedicated open-time column and a bare `"date"`/`"time"` column no import
#: source splits further.
_ALIASES: dict[str, tuple[str, ...]] = {
    "open_time": ("open_time", "opentime", "date", "time", "datetime"),
    "open_price": ("open_price", "open"),
    "high_price": ("high_price", "high"),
    "low_price": ("low_price", "low"),
    "close_price": ("close_price", "close"),
    "volume": ("volume", "vol"),
    "close_time": ("close_time", "closetime"),
    "quote_asset_volume": ("quote_asset_volume",),
    "number_of_trades": ("number_of_trades", "trades"),
    "taker_buy_base_asset_volume": ("taker_buy_base_asset_volume",),
    "taker_buy_quote_asset_volume": ("taker_buy_quote_asset_volume",),
}

_REQUIRED_FIELDS = (
    "open_time",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
)

#: `BUG-022`'s convention, reused so an imported file's `close_time` sorts
#: and compares exactly like every candle this app fetches from Binance
#: itself: the last instant the bar covers, one interval minus 1ms after
#: `open_time`, never the next bar's own open instant.
_CLOSE_TIME_IS_INCLUSIVE_BY = 1e-3

#: A `YYYY.MM.DD` date has exactly two separators — the count `_normalize_
#: timestamp_text()` checks before treating a dotted date part as
#: MetaTrader's format rather than a time portion's fractional seconds.
_DOTTED_DATE_SEPARATOR_COUNT = 2


@dataclass(frozen=True)
class CsvKlineParseResult:
    """`klines` in file order; `warnings` names every skipped row (1-based,
    matching what a spreadsheet shows) and why, so a partially-malformed
    file still imports its good rows instead of failing all-or-nothing."""

    klines: list[MarketData]
    warnings: list[str]


def _find_column(header: list[str], field: str) -> int | None:
    lowered = [name.strip().lower() for name in header]
    for alias in _ALIASES[field]:
        if alias in lowered:
            return lowered.index(alias)
    return None


def _find_column_by_alias(header: list[str], alias: str) -> int | None:
    lowered = [name.strip().lower() for name in header]
    return lowered.index(alias) if alias in lowered else None


def _normalize_timestamp_text(text: str) -> str:
    """MetaTrader's `Date` column is dot-separated (`2024.01.15`), which
    `datetime.fromisoformat()` cannot parse; some spreadsheet exports use
    `/` instead of `-`. Only the date portion is touched — a `.` in the
    time portion's fractional seconds (`00:00:00.123456`) must survive
    untouched, so `.` is only normalized when the date part itself has
    exactly the two separators a `YYYY.MM.DD` date has."""
    text = text.replace("/", "-")
    date_part, sep, rest = text.partition(" ")
    if date_part.count(".") == _DOTTED_DATE_SEPARATOR_COUNT and "-" not in date_part:
        date_part = date_part.replace(".", "-")
    return date_part + sep + rest


def _parse_timestamp(raw: str) -> datetime:
    """A bare numeric string is a unix timestamp (seconds, or milliseconds
    when large enough that seconds would land past year 5000) — the
    convention every one of TradingView/Binance/a spreadsheet's own epoch
    export already uses. Anything else is parsed as ISO-8601 (accepts
    `YYYY-MM-DD`, `YYYY-MM-DD HH:MM:SS`, and the same with a `T` separator
    and/or a UTC offset)."""
    text = raw.strip()
    if text.lstrip("-").isdigit():
        value = int(text)
        if abs(value) >= 10**12:
            value //= 1000
        return datetime.fromtimestamp(value, UTC)
    return datetime.fromisoformat(_normalize_timestamp_text(text)).replace(tzinfo=UTC)


def parse_csv_klines(
    csv_text: str, symbol: str, interval: TimeFrame
) -> CsvKlineParseResult:
    """`symbol`/`interval` are supplied by the caller (the Import dialog's
    own selection), never read from the file — no source this parser
    supports names the trading pair or timeframe as a column at all."""
    reader = csv.reader(StringIO(csv_text))
    try:
        header = next(reader)
    except StopIteration:
        return CsvKlineParseResult(klines=[], warnings=["File is empty."])

    columns = {field: _find_column(header, field) for field in _ALIASES}
    missing = [field for field in _REQUIRED_FIELDS if columns[field] is None]
    if missing:
        return CsvKlineParseResult(
            klines=[],
            warnings=[f"Missing required column(s): {', '.join(missing)}."],
        )

    # MetaTrader's own two-column export (`Date,Time,...`) has never actually
    # been joined here — `open_time`'s alias table matches `date` alone
    # first, so the separate `Time` column was silently ignored, dropping
    # every row's time-of-day. Detected independently of `_ALIASES
    # ["open_time"]`'s own match: a bare `date` column has no fixed meaning
    # (it may already carry a full timestamp, as MetaTrader's single-column
    # export does), but a `date` column *and* a separate `time` column next
    # to it is unambiguous.
    date_col = _find_column_by_alias(header, "date")
    time_col = _find_column_by_alias(header, "time")
    has_separate_date_and_time = date_col is not None and time_col is not None
    # `has_separate_date_and_time` above already guarantees both are `int`
    # when true; these are only read from inside that branch below.
    date_col_index = cast(int, date_col)
    time_col_index = cast(int, time_col)

    interval_seconds = interval.to_seconds()
    klines: list[MarketData] = []
    warnings: list[str] = []
    # `missing` above already returned early if any of these five were
    # `None`, so every remaining row can index by them directly — cast lets
    # mypy see what that early return already guarantees at runtime.
    open_time_col = cast(int, columns["open_time"])
    open_price_col = cast(int, columns["open_price"])
    high_price_col = cast(int, columns["high_price"])
    low_price_col = cast(int, columns["low_price"])
    close_price_col = cast(int, columns["close_price"])

    for row_number, row in enumerate(reader, start=2):
        try:
            open_time_text = (
                f"{row[date_col_index]} {row[time_col_index]}"
                if has_separate_date_and_time
                else row[open_time_col]
            )
            open_time = _parse_timestamp(open_time_text)
            close_time_index = columns["close_time"]
            if close_time_index is not None:
                close_time = _parse_timestamp(row[close_time_index])
            else:
                close_time = datetime.fromtimestamp(
                    open_time.timestamp()
                    + interval_seconds
                    - _CLOSE_TIME_IS_INCLUSIVE_BY,
                    UTC,
                )
            klines.append(
                MarketData(
                    symbol=symbol,
                    interval=interval.value,
                    open_time=open_time,
                    open_price=float(row[open_price_col]),
                    high_price=float(row[high_price_col]),
                    low_price=float(row[low_price_col]),
                    close_price=float(row[close_price_col]),
                    volume=float(row[columns["volume"]])
                    if columns["volume"] is not None
                    else 0.0,
                    close_time=close_time,
                    quote_asset_volume=float(row[columns["quote_asset_volume"]])
                    if columns["quote_asset_volume"] is not None
                    else 0.0,
                    number_of_trades=int(float(row[columns["number_of_trades"]]))
                    if columns["number_of_trades"] is not None
                    else 0,
                    taker_buy_base_asset_volume=float(
                        row[columns["taker_buy_base_asset_volume"]]
                    )
                    if columns["taker_buy_base_asset_volume"] is not None
                    else 0.0,
                    taker_buy_quote_asset_volume=float(
                        row[columns["taker_buy_quote_asset_volume"]]
                    )
                    if columns["taker_buy_quote_asset_volume"] is not None
                    else 0.0,
                )
            )
        except (ValueError, IndexError) as exc:
            warnings.append(f"Row {row_number}: {exc}")

    return CsvKlineParseResult(klines=klines, warnings=warnings)

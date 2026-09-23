# BUG-135 — MetaTrader CSV import silently drops time-of-day or rejects every row

- **Reported:** 2026-09-23 (independent PR review of `PR #257`, BOT-112D's own reviewer session)
- **Severity:** 🟡 P2 — a real MetaTrader export either imports every candle with its time-of-day silently zeroed (two-column `Date,Time` case) or imports zero rows at all (dot-separated `Date`, e.g. MT4/5's real `2024.01.15`), while the parser reports success/partial-success rather than failing loudly. `BOT-112D`'s own backlog names MetaTrader CSV as a required supported format.
- **Status:** ✅ Fixed (2026-09-23)
- **Context:** Market data import (`BOT-112D`) → `modules/market_data` → `domain/csv_kline_parser.py`
- **Environment:** App on `claude/bot-112d-063-039-batch`, Python 3.12, no display needed (pure parsing, no Qt).

## Reproduction

1. Import a MetaTrader-style CSV with separate `Date`/`Time` columns, e.g. header `Date,Time,Open,High,Low,Close,Volume` with a row `2024.01.15,13:45,100,105,95,102,1000`.
2. **Expected:** the row imports with `open_time = 2024-01-15 13:45:00 UTC`.
3. **Actual (before fix):** `datetime.fromisoformat("2024.01.15")` raises `ValueError: Invalid isoformat string: '2024.01.15'`; the row is skipped with a warning, and every row in a real MT4/5 export fails the same way — "No valid candles found in file." Confirmed directly:
   ```
   >>> from datetime import datetime
   >>> datetime.fromisoformat("2024.01.15")
   ValueError: Invalid isoformat string: '2024.01.15'
   ```
4. A variant with an ISO-formatted `Date` column and a separate `Time` column would instead import successfully but silently drop every row's time-of-day, because `_find_column()`'s alias table matched `Date` alone and never looked for a companion `Time` column at all.

## Symptom

```
ValueError: Invalid isoformat string: '2024.01.15'
```
(raised inside `_parse_timestamp()`, caught per-row by `parse_csv_klines()`'s own `except (ValueError, IndexError)`, surfacing only as a per-row import warning — or, for the two-column case, no error at all, just wrong data.)

## Root cause

`csv_kline_parser.py`'s own module docstring already documented the intended MetaTrader shape ("`Date,Time,...` ... or `Date` alone, space-joined with `Time`") but the join was never implemented: `_ALIASES["open_time"]` listed `"date"` and `"time"` as two candidates for the *same* single column, so `_find_column()` matched whichever came first (`"date"`) and never combined a companion `"time"` column at all. Separately, `_parse_timestamp()` normalized `/` to `-` for slash-separated dates but never normalized MetaTrader's dot separator (`2024.01.15`), which `datetime.fromisoformat()` cannot parse in any form.

## Fix

`csv_kline_parser.py`:
- Added `_find_column_by_alias()` and, in `parse_csv_klines()`, an explicit check for a `date` column *and* a separate `time` column both present — when both exist, their raw values are space-joined into one timestamp string before parsing, rather than reading `date` alone. A bare `date` column with no companion `time` column keeps its prior behavior (already-full timestamp).
- Added `_normalize_timestamp_text()`: normalizes a dot-separated date part (`2024.01.15` → `2024-01-15`) before handing the string to `datetime.fromisoformat()`, scoped to only the date portion of the string so a time portion's fractional-seconds dot (`00:00:00.123456`) is never touched.
- Updated the module docstring to describe what is now actually implemented instead of an aspirational shape.

## Regression test

- `tests/unit/modules/market_data/domain/test_csv_kline_parser.py::test_real_metatrader_export_joins_dotted_date_with_separate_time_column` — a real MT4/5-shaped `Date,Time` header with a dotted date (`2024.01.15,13:45`); failed before the fix with the exact `ValueError` above, passes after with `open_time == datetime(2024, 1, 15, 13, 45, tzinfo=UTC)`.
- `tests/unit/modules/market_data/domain/test_csv_kline_parser.py::test_metatrader_export_with_only_a_date_column_still_reads_full_timestamp` — confirms the pre-existing single-`Date`-column behavior is unchanged (the join only engages when both columns exist).

## Verification

```
cd /tmp/batch6-work/Sagittarius_Elite_Warrior && PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit -q
```
5114 passed (full `tests/unit` suite, including both new regression tests and the two pre-existing MetaTrader-shaped tests, confirming no regression). `ruff check`/`ruff format --check src tests tools scripts` clean. Mypy (`src` + `scripts`, this repo's own `ci-local.ps1` invocation): `Success: no issues found in 660 source files`.

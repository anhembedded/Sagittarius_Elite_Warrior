# BUG-240 — A chart's time axis shows every tick in today's UTC offset, so ticks across a daylight-saving change are an hour off

- **Reported:** 2026-10-20 (found while fixing `BUG-239`; confirmed by the independent reviewer of PR #636, who asked for it to be filed: https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/636#issuecomment-6293080831)
- **Severity:** 🟢 P3 — in a zone that observes daylight saving, the part of a chart's history on the other side of the change reads one hour off on its axis. No order or stored data is affected; the owner's `+07` machine has no daylight saving and is not affected.
- **Status:** Open
- **Board:** Charts' time axes apply the UTC offset in force now to every tick, so history across a daylight-saving change is an hour off on the axis, for every zone that observes it (named ones such as `America/New_York` included, not only "System").
- **Context:** Any chart (Backtest, Bots) → `src/support/charting/chart_card/` → `plot_layout.py`
- **Environment:** Found by code reading at `5e7d00f`; not yet reproduced on screen.

## Reproduction
Not yet reproduced on screen. Expected from the code: with the display zone `America/New_York` (or "System" on such a machine) on a day when it is on daylight saving time, scroll a chart back to January: the axis ticks read EDT (UTC-04:00) times, one hour later than the crosshair label and the trades table, which convert each instant by its own rules (`display_timezone_service.get_utc_offset_seconds` per timestamp).

## Symptom
Not yet captured. Expected instead: an axis tick and a table cell for the same instant read the same time.

## Root cause
Not yet established. Suspected: at `cb87606`, `plot_layout.py` computes one offset with `get_utc_offset_seconds(datetime.now(UTC).timestamp(), zone)` in `__init__`, `set_display_timezone` and `add_subplot` and passes it as `pg.DateAxisItem(utcOffset=…)`, which shifts every tick by that one number.

## Fix
Not yet. Likely a `DateAxisItem` subclass that converts each tick with the service per instant, in one place for all three sites (`fix-bug-rule.md` §1).

## Regression test
Pending.

## Verification
Not run.

## Suggested next steps
Reproduce on screen with a DST zone and an injected `machine_local_time`; then write the per-instant axis test red before the fix.

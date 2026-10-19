# BUG-232 — The "System" display time zone shows UTC on a machine whose zone is not UTC

- **Reported:** 2026-10-19 (review of PR #586, `BOT-181`, by the independent reviewer session; confirmed by probe)
- **Severity:** 🟡 P2 — a screen that is told to show the machine's local time shows UTC, labelled as the system zone; a Vietnamese owner reads times seven hours off. No order or stored data is affected.
- **Status:** Open
- **Board:** Choosing "System" as the display time zone silently shows UTC on any machine whose zone name is not an IANA key (`+07`, `EDT`, `BST`, a Windows display name): the zone lookup returns the abbreviation, `ZoneInfo` cannot resolve it, and it falls back to UTC with a WARNING.
- **Context:** Backtest mode's display time zone setting (and any screen using `AppValueFormatter(SYSTEM_TIMEZONE_KEY)`) → `src/support/ui_kit/` → `services/display_timezone_service.py`
- **Environment:** Probed on Linux, `TZ=Asia/Ho_Chi_Minh`, `TZ=America/New_York`, `TZ=Europe/London`, app at `master-warrior` 8d63158. Windows inferred from the same code path, not run.

## Reproduction
1. Run with `TZ=Asia/Ho_Chi_Minh` (or the OS zone set to Vietnam).
2. Call `get_system_timezone_name()`: it returns `'+07'`.
3. Call `resolve_zone_info("SYSTEM")` or `format_display_datetime(dt, "SYSTEM")`: `ZoneInfo('+07')` raises, a WARNING `App.DisplayTimezone` is logged, and UTC is used.
Expected: the machine's own zone (`2026-10-19 19:01:30` for `12:01:30Z`). Actual: `12:01:30`. Frequency: every call on a non-UTC machine.

## Symptom
Reviewer probe at `4e27851` for a pause beginning `2026-10-19 12:00:00Z` lasting 90 s:

| `TZ` | system name | true local end | shown |
|---|---|---|---|
| Asia/Ho_Chi_Minh | `'+07'` + WARNING | 19:01:30+07:00 | 12:01:30 |
| America/New_York | `'EDT'` + WARNING | 08:01:30-04:00 | 12:01:30 |
| Europe/London | `'BST'` + WARNING | 13:01:30+01:00 | 12:01:30 |

## Root cause
Not yet established beyond the mechanism read at `8d63158`: `get_system_timezone_name` returns `str(datetime.now().astimezone().tzinfo)`, which is the zone's abbreviation (or, on Windows, a display name), never an IANA key; `resolve_zone_info` passes it to `ZoneInfo` and falls back to UTC on failure. The service has no way to ask the platform for the IANA key with the stdlib alone; `astimezone()` with no argument is the stdlib's way to use the machine's zone without naming it.

## Fix
Pending. Direction: resolve `SYSTEM` to the machine's fixed-offset-aware conversion (`dt.astimezone()`), not to a `ZoneInfo`, so no key is needed; the label can name the abbreviation. `BOT-181` already avoids the service for the same reason (its pause end is written with `astimezone()` and its UTC offset).

## Regression test
Pending: a test that pins a non-UTC machine zone (an injected zone, since `time.tzset` does not exist on Windows) and fails when "System" falls back to UTC; it must be red on a UTC runner too.

## Verification
Not run.

## Suggested next steps
- Fix inside `BOT-162` only if that task cannot meet its acceptance criteria without it (coordinator decision, 2026-10-19); otherwise a task of its own.
- Check the Backtest display-zone picker for the same fallback.

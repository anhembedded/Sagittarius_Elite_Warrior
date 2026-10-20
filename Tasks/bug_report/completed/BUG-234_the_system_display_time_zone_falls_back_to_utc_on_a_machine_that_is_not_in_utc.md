# BUG-234 — The "System" display time zone shows UTC on a machine whose zone is not UTC

- **Reported:** 2026-10-19 (review of PR #586, `BOT-181`, by the independent reviewer session; confirmed by probe)
- **Severity:** 🟡 P2 — a screen that is told to show the machine's local time shows UTC, labelled as the system zone; a Vietnamese owner reads times seven hours off. No order or stored data is affected.
- **Status:** ✅ Fixed (2026-10-20)
- **Board:** "System" display time zone showed UTC on any machine whose zone name is not an IANA key (`+07`, `EDT`, `BST`). Cause: the zone's abbreviation was looked up as a `ZoneInfo` key and failed over to UTC. Fixed: "System" is converted by the OS per instant (`datetime.astimezone()`), never looked up by name; a failed lookup is logged once.
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
At `01d188a`, `src/support/ui_kit/services/display_timezone_service.py:27` (`get_system_timezone_name`) returns `str(datetime.now().astimezone().tzinfo)`: the platform's abbreviation (`+07`, `EDT`, `BST`) or, on Windows, a display name such as `SE Asia Standard Time`, never an IANA key. `resolve_zone_info` (`:35`) passes it to `ZoneInfo(sys_name)` (`:47`), which raises, and the `except` (`:48-52`) returns UTC with a WARNING. Every consumer reached the zone through that one function (`format_display_datetime` `:117`, `get_utc_offset_seconds` `:147`, `run_texts.zone_name` `run_texts.py:35` via `.key`), so the chart axis, trade tables, run texts and the label all shared the fault. The design error: "System" was modelled as a named zone, and the stdlib cannot name the machine's zone. The gate was green because the only test (`test_resolve_zone_info_system`) asserted `is not None`, which the UTC fallback satisfies; the CI runner is UTC, where the fallback is correct. No other path resolves "System": the log viewer and `order_failure` already use `astimezone()`.

## Fix
`display_timezone_service.py`: one converter, `to_display_time(moment, tz_name)`, used by `format_display_datetime`, `get_utc_offset_seconds` and (through `display_zone_name`) the run texts. "System" is `machine_local_time(moment)`, i.e. `moment.astimezone()`: the OS converts each instant by its own rules, so daylight saving is right per instant (a July backtest shown in January keeps July's offset) on Windows and Linux, and no key is needed. No new dependency (`tzlocal` would be one; not added). `resolve_zone_info` is gone from the public surface: a function returning a `ZoneInfo` for "System" is what made the trap. `get_system_timezone_name` now names the zone for labels and texts from the OS answer (`UTC+07:00`, `EDT, UTC-04:00`). If the OS cannot convert an instant (`OSError`/`OverflowError`/`ValueError`, e.g. a pre-1970 instant on Windows), the result is UTC with one WARNING per distinct reason (`App.DisplayTimezone`), not one per table cell. The log template catalogue is regenerated.

## Regression test
`tests/unit/support/ui_kit/services/test_system_display_timezone.py`: `test_system_shows_the_machines_own_time` (Vietnam, New York, London), `test_system_follows_daylight_saving_per_instant`, `test_system_zone_is_named_by_the_text_that_was_written_in_it`, `test_a_machine_that_cannot_answer_falls_back_to_utc_and_says_so`, `test_the_fallback_is_logged_once_not_once_per_cell`, `test_utc_machine_is_named_utc`. The machine is injected through `machine_local_time`, answering with the fixed-offset zone `astimezone()` returns, so no test reads the runner's `TZ`. Before the fix (run on a UTC runner) it failed with `'2026-10-19 12:01:30' != '2026-10-19 19:01:30'` (and the 08:01:30 / 13:01:30 variants): the report's symptom; after, all pass.

## Verification
- Regression file red before the fix (5 of the first 6 tests failed, for the reasons above), green after; touched suites (`ui_kit/services`, `backtesting/ui/logic`, `backtesting/ui/view_models`, `modules/trading/ui`): 867 passed.
- Real machine zone on Linux, same code: `TZ=Asia/Ho_Chi_Minh` -> `System (UTC+07:00)`, `2026-10-19 19:01:30`, January offset 25200 s; `TZ=America/New_York` -> `System (EDT, UTC-04:00)`, `08:01:30`, January offset -18000 s; `TZ=UTC` -> `System (UTC)`, `12:01:30`. Windows is not run here: it takes the same `astimezone()` path (CPython reads the Windows zone through the C runtime), and its display name is only a label.
- Commit tier and the `-Full` run: see the pull request.

# BUG-239 — A text that shows a moment under the "System" time zone names today's UTC offset, not the moment's

- **Reported:** 2026-10-20 (retroactive review of PR #621, `BUG-234`, by the independent reviewer session: https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/621#issuecomment-6292500140; reproduced)
- **Severity:** 🟢 P3 — on a machine whose zone observes daylight saving, the zone named after a time can be the wrong one (`EDT, UTC-04:00` after a January time that is EST). The time itself is right; no order or stored data is affected; the owner's `+07` machine has no daylight saving and is not affected.
- **Status:** ✅ Fixed (2026-10-20)
- **Board:** The "System" time zone's name in run texts came from today's clock, so a moment in the other half of the year was labelled with the wrong offset (`2026-01-15 07:00:00 EDT, UTC-04:00`; it is EST). Cause: `get_system_timezone_name` read `datetime.now`. Fixed: the name comes from the shown moment's own conversion (`system_zone_name_at`), and a range whose bounds differ in offset names each bound's own.
- **Context:** Backtest run texts (report import, session history, data sync, strategy config, config diff) → `src/modules/backtesting/ui/logic/run_texts.py` → `src/support/ui_kit/services/display_timezone_service.py`
- **Environment:** Linux, `TZ=America/New_York`, run on 2026-10-20 (EDT), app at `5e7d00f`. Windows not run: the same `astimezone()` path.

## Reproduction
1. `TZ=America/New_York`, on a day when New York is on daylight saving time.
2. `zoned_moment_text(datetime(2026, 1, 15, 12, tzinfo=UTC), "SYSTEM")`.
Expected: `2026-01-15 07:00:00 EST, UTC-05:00`. Actual: `2026-01-15 07:00:00 EDT, UTC-04:00`. Frequency: every call whose moment and today are on opposite sides of a daylight-saving change.

## Symptom
Reviewer probe at `6d7ccdd` (`BUG-234`'s squash) and the same probe at `5e7d00f` before this fix: `2026-01-15 07:00:00 EDT, UTC-04:00`. 07:00 on 15 January in New York is EST (UTC-05:00), so the text names a zone the time was not written in, against `display_zone_name`'s own contract.

## Root cause
At `5e7d00f`, `display_timezone_service.py` → `get_system_timezone_name` built the name from `to_display_time(datetime.now(UTC), "SYSTEM")`, so `display_zone_name("SYSTEM")` and, through it, `run_texts.py` → `zone_name` / `zone_suffix` / `zoned_moment_text` named the offset in force now. The conversion of the moment itself (`to_display_time` → `machine_local_time`) was already per instant, so the time and its label came from two different instants. The design error: the label was a function of the setting alone, while a label on a text is a function of the setting *and the moment*. Every text that names its zone went through that one function: `zoned_moment_text` (report import, session history, data sync, strategy config) and `time_range_diff_text` (the run config diff, `backtest_fsm_matrix.py` → `compute_diff_summary`).

Two other readers of "now" were checked and are not this defect: `get_display_timezone_label` / `get_supported_timezones` label the *setting* in a picker, which names the zone the person is in today, so they keep today's offset by design. The chart's `DateAxisItem` takes one offset computed at `datetime.now` (`src/support/charting/chart_card/plot_layout.py`, `__init__`, `set_display_timezone`, `add_subplot`); that is a different defect (an offset applied to every tick of the axis, not a label) and is out of this fix's scope.

## Fix
`display_timezone_service.py`: `system_zone_name_at(moment)` names the zone from `to_display_time(moment, "SYSTEM")`; `display_zone_name(tz_name, moment)` takes the moment (required, no default, so a caller cannot slip back into "now"); `get_system_timezone_name()` is `system_zone_name_at(now)`, kept for the picker only and documented as the setting's label. `run_texts.py`: `zone_name` and `zone_suffix` take the moment; `zoned_moment_text` passes its own. `time_range_diff_text` collects the range's four bounds: when they share one label it names the zone once after the range as before; when a daylight-saving change lies between them, each bound names its own. A range with no concrete bound (both ends open) uses today's label, there being no moment to name. `.claude/rules/capabilities.md` regenerated (new `Use:` symbol).

## Regression test
`tests/unit/support/ui_kit/services/test_system_display_timezone.py`: `test_a_text_names_the_offset_of_the_moment_it_shows_not_of_today` (January and July, so it is red in either half of the year), `test_a_range_across_a_daylight_saving_change_names_each_bound_in_its_own_offset`, `test_a_range_inside_one_offset_names_the_zone_once`. The machine is injected through `machine_local_time`, so no test reads the runner's `TZ`. Red before the fix on 2026-10-20 (New York on EDT) for the right reason: `'2026-01-15 07:00:00 EDT, UTC-04:00' != '2026-01-15 07:00:00 EST, UTC-05:00'`, and the two range tests; green after. `test_display_timezone_service.py` now passes a moment to `display_zone_name`.

## Verification
- Regression tests: 3 red before, all green after (12 in the file).
- `tests/unit/support`, `tests/unit/modules/backtesting`, `tests/unit/architecture`, `tests/integration/modules/backtesting`: 3970 passed.
- Real machine zone, same code: `TZ=America/New_York` → `2026-01-15 07:00:00 EST, UTC-05:00` and `2026-07-15 08:00:00 EDT, UTC-04:00`; before the fix the January text read `EDT, UTC-04:00`.
- Commit tier and the `-Full` run: see the pull request.

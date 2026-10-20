# BOT-205 — The Bots chart follows the display time zone the owner chooses, "System" included

**Status:** ✅ Done (2026-10-20)
**Board:** The selected bot's chart axis, crosshair label and Fills "Time" column follow one app-wide display time zone (UTC, System, or an IANA zone) that the Backtest screen now shares, instead of a Backtest-only setting.
**Source:** the owner, 2026-10-20: "chart của bot, chưa có cơ chế chọn múi giờ. bên back test screen có cơ chế đó rùi, làm task luôn nhé" (the bot's chart has no way to choose the time zone; the Backtest screen already has one; create the task and do it).
**Risk:** 🟡 — the Backtest screen's remembered zone moves from its own slice to a shared one; the first start adopts the old value, so no choice resets.
**Complexity:** M — one shared preference, one selector on the Bots chart, the Fills table, and the Backtest following the shared value.
**Depends on:** BUG-234 (#621): `to_display_time` and `display_zone_name` convert "System" through the OS.

---

## 1. Context and problem
`ChartCard.set_display_timezone` exists (`src/support/charting/chart_card/chart_card.py`) and drives the date axes and the crosshair label through `display_timezone_service`. Only the Backtest screen calls it: its zone is a field of `TimeRangeViewModel` (`displayTimezone`), picked in the Run setup panel (`comboBacktestTimezone`) and remembered in the Backtest state slice (`backtest_state_fields.py`, field `timezone`). `BotChartHost.show` (`src/modules/bots/ui/bots_screen/bot_chart_host.py`) builds a `ChartCard` and never sets a zone, so a bot's chart reads in UTC on a machine whose owner lives in UTC+7, and its Fills "Time" column is UTC through `APP_VALUE_FORMATTER`.

## 2. Acceptance criteria
- [ ] The Bots screen offers the same zones as the Backtest screen (`get_supported_timezones`: UTC, System, Asia/Ho_Chi_Minh, …) in the header of the selected bot's chart.
- [ ] The chart's time axis and crosshair label follow the choice. Under "System" with the machine zone injected as UTC+7 they show local time, not UTC (red before this change).
- [ ] The choice is one app-wide setting: changing it on one screen changes the other, and it is remembered across sessions.
- [ ] The Bots Fills "Time" column follows the choice.
- [ ] The Backtest screen behaves as before, but reads and writes the shared setting.
- [ ] Preview frames show the selector on the Bots chart.

## 3. Design
**One shared setting, not per screen.** The Backtest zone was not deliberately per screen: `BOT-097` and `EPIC-003F3` store it on the Backtest view model because the Backtest was the only screen with a chart that needed one; no decision record says it must differ per screen. A display zone is a property of the person's clock, so `DisplayTimezonePreference` (`src/support/ui_kit/services/`) holds it for the whole application, follows the pattern of `SymbolPreferences` (an `IStateContributor` registered once in `remembered_state_wiring.py`, found with `find_*` and a private fallback outside the full app).

**One converter.** Everything keeps going through `display_timezone_service` (`to_display_time`, `format_display_datetime`, `get_utc_offset_seconds`); nothing converts a time on its own.

**Selector.** `DisplayTimezoneCombo` (`src/support/ui_kit/`) is a stock `QComboBox` fed by `get_supported_timezones` (short labels; the full label is each item's tooltip), shown in the chart card's own header (`ChartCard.add_to_header`), so the screen's layout does not move (EPIC-040 reshapes the centre in parallel; an extra row above the chart also broke the small-window height budget of `test_bots_view.py`). The Backtest keeps its Run setup combo, which is wired to the same shared setting.

**What follows.** `BotChart.use_display_timezone` (`src/modules/bots/ui/chart/bot_chart.py`) sets the chart's zone, adds the selector to the card header and follows the shared setting until `shutdown`; `BotFillsPanel.use_display_timezone` writes the Fills "Time" column through `ZonedValueFormatter` and writes the rows again on a change. The Backtest follows the same setting through `follow_shared_display_timezone` (wired in `signal_wiring.connect_ui_signals`); its own `timezone` field left the Backtest state slice. **No reset (coordinator decision, owner's standing pre-approval, 2026-10-20):** `DisplayTimezonePreference.adopt_earlier_zone`, called once in `remembered_state_wiring.py` with the Backtest slice's old `timezone` (read through `UiStateCoordinator.read`), starts the shared setting from that zone when it has no value of its own; a zone no picker offers is ignored. A silent reset to UTC is what BUG-234 was about.

**Texts that do not follow.**
- The Grid backtest page's result chart (`GridBacktestView`, under the Backtest tab) keeps UTC: its range editors are labelled UTC and EPIC-040 reshapes that page; it is a one-call follow-up (`BotChart.use_display_timezone`) once the page has settled.
- Ladder labels on the chart and "Last price heard" are prices; they carry no time.
- The Log tab stamps each line with the machine's own clock when the line is written (`logging.Formatter`, `%H:%M:%S`); it is an audit trail beside the log files, which use the same machine time, and a line written earlier cannot be re-stamped. It stays machine time.

## 3a. Reuse
- Show a time in the user's display timezone: used `to_display_time` / `get_utc_offset_seconds` / `get_supported_timezones` via `ChartCard.set_display_timezone`; no second converter.
- Table values in the display zone: used `ZonedValueFormatter` for the Fills table.
- Remembered shared preference: used the `IStateContributor` pattern of `SymbolPreferences`.
- A pick-one field: used a stock `QComboBox`, as the Backtest Run setup panel does.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/ui_kit/services/display_timezone_preference.py` | the shared, remembered setting |
| `src/support/ui_kit/display_timezone_combo.py` | the selector |
| `src/presentation/ui/remembered_state_wiring.py` | register the preference |
| `src/modules/bots/ui/chart/bot_chart.py`, `preview.py` | the chart follows the setting and offers the selector |
| `src/modules/bots/ui/bots_screen/*` | dependencies carry the setting; the chart ports and the Fills panel use it |
| `src/modules/backtesting/ui/logic/shared_display_timezone.py`, `signal_wiring.py`, `backtest_state_fields.py` | the view model follows the shared setting; the own `timezone` state field leaves |
| `tests/…` | see 5 |

## 5. Testing
Unit tier; QtWidgets offscreen.
| Criterion | Proof |
| :--- | :--- |
| the Bots chart offers the zones | `test_bot_chart_display_timezone.py::test_the_chart_header_holds_a_selector_that_writes_the_shared_zone`; `test_display_timezone_combo.py` |
| axis and crosshair follow; System with an injected UTC+7 machine shows local time | `test_bot_chart_display_timezone.py` (4 tests); red before: with the line that applies the zone removed, 3 of them fail with `assert 0.0 == 25200` (the axis stays at UTC) |
| an earlier Backtest zone is adopted once, not reset | `test_display_timezone_adopts_the_backtest_zone.py` (red before: `'UTC' == 'Asia/Ho_Chi_Minh'`) |
| one app-wide, remembered setting | `test_display_timezone_preference.py`; `test_shared_display_timezone.py`; `test_backtest_timezone_presenter.py::test_the_backtest_follows_the_applications_display_zone_both_ways` (fails with the wiring line removed) |
| Fills "Time" column | `test_bot_fills_display_timezone.py` (the panel, and the screen over its own composition) |
| Backtest unchanged | the existing Backtest suites, green |
| preview | `src/modules/bots/ui/chart/preview.py` (`bot_chart`) shows the selector in the header, set to Asia/Ho_Chi_Minh |

## 6. Docs touched
none, because `Docs/MODULES/bots/` states nothing about the chart's header, its time axis or a display zone (`grep` for chart, display zone and time zone found no hit); the PR says `No design change`. `.claude/rules/capabilities.md`'s generated block gains one row (`python3 scripts/render_capability_index.py --write`).

## Implementation notes (written when done)

## Resume
Started 2026-10-20 on branch `claude/bot-205-bots-chart-display-timezone`.

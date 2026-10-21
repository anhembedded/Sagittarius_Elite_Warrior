# EPIC-036D6 — The owner sets the quiet hours on the Options page

**Status:** ✅ Done (2026-10-21)
**Source:** the coordinator, 2026-10-21: *"Proceed with schedule, then routing matrix"*; design N1–N8 ("a schedule", `EPIC-036D`).
**Risk:** 🟢 — a settings group; the hub already holds Warning and Info during quiet hours and Critical never waits
**Complexity:** M — a presenter split first, then the group
**Epic:** [EPIC-036](../README.md); a slice of [EPIC-036D](../incomplete/EPIC-036D_alerts_ui.md)
**SPEC:** [SPEC-017](../../../../Docs/SPEC/SPEC-017_set_up_an_alert_channel.md) step 7
**Depends on:** [EPIC-036D4](EPIC-036D4_telegram_on_the_options_page.md)

---

## 1. Context and problem
`AlertHub` holds Warning and Info while `AlertSettings.quiet_hours` says it is quiet (`QuietHoursHold`), but nothing could set `quiet_hours`: `JsonAlertSettings.current()` never filled it. The owner had no way to choose a quiet night.

## 2. Acceptance criteria
- [x] **The period is kept across a restart** in the settings file beside the bot modes, and reaches the hub as a zone-aware `QuietHours`. (`test_quiet_hours_survive_a_restart_and_reach_the_hub_as_a_zone_aware_period`)
- [x] **Setting one thing keeps the other.** A bot's mode and the quiet hours are written together. (`test_setting_a_bots_mode_keeps_the_quiet_hours_and_the_other_way_round`)
- [x] **A bad entry is off, never a hold.** A `quiet_hours` entry this build cannot read is ignored and told once; the modes are kept. (`test_a_quiet_hours_entry_this_build_cannot_read_is_off_told_and_the_modes_kept`)
- [x] **The same start and end is refused**, in words, and nothing is kept. (`test_the_same_start_and_end_is_refused_and_nothing_is_kept`, `test_the_same_time_twice_is_refused_in_words_and_nothing_is_kept`)
- [x] **The zone is the display zone at the moment of saving**, kept by name; a later change of the display zone does not move a set night; `SYSTEM` is the machine's clock, not a label. (`test_a_period_is_kept_in_the_zone_of_the_moment_it_was_saved`, `test_the_machines_own_clock_is_kept_as_system_and_reaches_the_hub_without_a_name`, `test_the_machines_clock_decides_not_utc`, `test_daylight_saving_moves_the_machines_night`, `test_system_stays_system_not_a_label_with_an_offset`, `test_a_name_that_is_no_zone_is_refused_before_anything_is_written`, `test_the_hubs_view_never_raises_even_if_a_bad_name_got_in`)
- [x] **A store that cannot write is told**, not reported saved; a read-only copy changes nothing and says why. (`test_a_store_that_cannot_write_is_told_not_reported_saved`, `test_a_read_only_copy_offers_no_change_and_says_why`)
- [x] **The group**: check box, From, To, one line of what is set, Save; Save with the box cleared turns it off; off the UI thread, button off while the work is out. (`test_alerts_page_quiet_hours.py`)
- [x] **Frames**: the page with the group, light and dark, three widths (`alerts_options@WxH.png`, artifact `ui-screenshots`).
- [ ] **The owner's look at the real window** (SPEC-017): not run.

## 3. Design
- **One page, so a presenter split first.** A module owns one Options page (`ContributionRegistry.contribute_options_page`), and the page's presenter was at 398 of 400 lines. The Bots list (`BotModeList`) moved out; no behaviour changed.
- **Immediate-apply like the rest of the page.** Save acts at once; OK and Apply have nothing to save here. The check box is what the group means, so there is no second "off" control.
- **The zone is a name, taken at save.** `QuietHoursChoice.zone_key` is `UTC`, an IANA name, or `SYSTEM` for the machine's own clock. `SYSTEM` is not turned into a name: the machine's zone has no IANA key the standard library can read (`BUG-234`), so `QuietHours.zone` is `None` there and the period is read on the OS's clock instant by instant, daylight saving included. A night set in Berlin stays Berlin's. (Review round 1 found the first cut stored a label such as `ICT, UTC+07:00`, which made `current()` raise on every alert until a restart; a name that is no zone is now refused before anything is written, and the hub's view never raises.)
- **Equal ends are refused**, not kept, because `QuietHours` reads them as no period.
- **Per-bot mute in the bots list: skipped** (decided by the coordinator for the owner): the bots list has no context menu and the Options page covers it.

## 3a. Reuse
`used`: `QuietHours` and `QuietHoursHold` (the hub's holding), `JsonAlertSettings` (one object, one file), `find_display_timezone_preference`, `AlertsActionRelay`, `ActionOwnershipTracker`. `not used`: a second Options page (refused by the registry).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `alerting/contracts/i_quiet_hours_setting.py` | the port and `QuietHoursChoice` |
| `alerting/adapters/json_alert_settings.py` | the `quiet_hours` key, read and written |
| `alerting/application/quiet_hours_setup.py` | choosing the period |
| `alerting/composition/settings_bindings.py` | the settings bindings (split from `alerting_bindings.py`) |
| `alerting/ui/options/bot_mode_list.py` | the Bots list, out of the presenter |
| `alerting/ui/options/quiet_hours_group.py`, `quiet_hours_view_model.py`, `quiet_hours_words.py`, `display_zone_key.py` | the group |
| `alerting/ui/options/alerts_settings_presenter.py`, `alerts_settings_view.py`, `alerts_settings_view_model.py`, `preview.py` | wiring |

## 5. Testing
Unit: `test_json_alert_settings.py`, `test_quiet_hours_setup.py`, `test_alerts_page_quiet_hours.py`; integration `test_alerts_options_page_frames.py`.

## 6. Docs touched
`Docs/MODULES/alerting/` README, 04, 05, 06, 08, 10; `Docs/SPEC/SPEC-017`.

## Implementation notes (written when done)
The presenter is at 399 of 400 lines again: the next group of the page (the routing matrix) needs its part moved out first, as this one needed the Bots list moved.

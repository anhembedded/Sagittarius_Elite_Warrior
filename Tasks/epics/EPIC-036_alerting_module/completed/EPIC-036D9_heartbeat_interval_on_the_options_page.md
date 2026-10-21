# EPIC-036D9 — The owner chooses how often the heartbeat is sent: the heartbeat interval on the Options page

**Status:** ✅ Done (2026-10-21)
**Source:** the coordinator, 2026-10-21: *"Go on with the heartbeat interval; that closes 036D."*; `EPIC-036D` §2 ("Schedule: heartbeat interval (default 6 h)"); `HeartbeatPolicy`'s docstring ("A UI to change both belongs to `EPIC-036D`").
**Risk:** 🟢 — a message that is sent more or less often; delivery is untouched, a bad value is the default
**Complexity:** M
**Epic:** [EPIC-036](../README.md); the last slice of [EPIC-036D](EPIC-036D_alerts_ui.md)
**SPEC:** [SPEC-017](../../../../Docs/SPEC/SPEC-017_set_up_an_alert_channel.md) step 10
**Depends on:** [EPIC-036D8](EPIC-036D8_channel_switches_on_the_options_page.md), [EPIC-036E](EPIC-036E_heartbeat_dead_mans_switch_and_summary.md)

---

## 1. Context and problem
`HeartbeatService` read its interval from a constant (`HeartbeatPolicy.heartbeat_every`, N4: six hours), so an owner who wanted a message every hour while watching a new bot, or once a day on a quiet account, had to edit code.

## 2. Acceptance criteria
- [x] **The interval is kept across a restart** and reaches the heartbeat on its next pass, with no restart; nothing chosen is the policy's own. (`test_a_chosen_interval_survives_a_restart_and_the_heartbeat_sees_it`, `test_an_interval_the_owner_chose_replaces_the_policys_and_applies_at_the_next_tick`, `test_with_no_interval_chosen_the_policys_applies`)
- [x] **Only the offered hours can be chosen** (`HEARTBEAT_HOURS_CHOICES`: 1, 2, 3, 6, 12, 24); choosing the default keeps no value, so a later change of the default still reaches the owner. (`test_every_offered_interval_is_kept_and_shown`, `test_choosing_the_default_keeps_no_value_so_a_later_default_still_reaches_the_owner`, `test_an_interval_that_is_not_offered_is_refused_and_nothing_is_kept`)
- [x] **A value this build does not offer in the file is the default, told once.** (`test_a_value_this_build_does_not_offer_is_the_default_told_once`)
- [x] **It is written beside the other settings** and costs none of them. (`test_the_interval_is_written_beside_the_other_settings_and_costs_none`)
- [x] **A read-only copy changes nothing and says why; a store that cannot write is told.** (`test_heartbeat_setup.py`)
- [x] **The page**: a "Heartbeat" group with one choice, acting at once, off while the work is out, the default marked, a read-only note, and after an unexpected failure the choice shows what was kept. (`test_alerts_page_heartbeat.py`)
- [x] **A second request while one is out is dropped**, from any group. (`test_a_request_made_while_another_is_out_is_dropped_not_queued`)
- [x] **Frames**: the page with the group, light and dark, three widths (`alerts_options@WxH.png`, artifact `ui-screenshots`).
- [ ] **The owner's look at the real window** (SPEC-017): not run.

## 3. Design
- **A choice from a short list, not a free number.** A free interval needs a bound anyone could argue with (a heartbeat every second is a flood, every month is no heartbeat); six values cover "often while I watch" to "once a day". The list is one constant (`HEARTBEAT_HOURS_CHOICES`), so a seventh is one more entry.
- **No "off".** The heartbeat is how the owner knows the bots are alive (N4); a switch to remove it is a different decision, listed as an extension case on the port.
- **The heartbeat reads the setting on every pass** (`AlertSettings.heartbeat_every`, `None` is the policy's own), like the hub reads the quiet hours, so there is nothing to restart. A shorter interval sends the next heartbeat at the next housekeeping pass when the last one is older than it.
- **The hour of the daily summary stays a constant**: nobody asked to change it, and the summary's hour is tied to the owner's working day (`HeartbeatPolicy`).
- **The presenter's two repeated pieces left it**: the "is another action out" guard is in `_begin` (it was copied into each handler), and showing a group from memory is `SettingPanels`.

## 3a. Reuse
`used`: `JsonAlertSettings` and `SettingsDocument` (one more key), `IAlertSettingsSource` (the heartbeat's read), the page's tracker and relay, `ActionResults`. `not used`: a free number field (see §3).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `alerting/contracts/i_heartbeat_setting.py`, `domain/alert_policies.py`, `domain/alert_settings.py` | the port, the choices, `heartbeat_every` on the read model |
| `alerting/adapters/settings_document.py`, `json_alert_settings.py`, `composition/settings_bindings.py` | the key, the fifth port, the binding |
| `alerting/application/heartbeat_service.py`, `composition/alerting_bindings.py` | reads the setting each pass |
| `alerting/application/heartbeat_setup.py` | choosing the interval |
| `alerting/ui/options/heartbeat_group.py`, `heartbeat_view_model.py`, `heartbeat_words.py` | the group |
| `alerting/ui/options/setting_panels.py`, `alerts_action_kind.py`, `action_results.py`, `alerts_settings_presenter.py`, `alerts_settings_view.py`, `alerts_settings_view_model.py`, `alerts_words.py`, `preview.py` | wiring |

## 5. Testing
Unit: `test_json_alert_settings_heartbeat.py`, `test_heartbeat_setup.py`, `test_heartbeat_service.py`, `test_alerts_page_heartbeat.py`; integration `test_alerts_options_page_frames.py`. Mutation-checked: the service ignoring the setting, no connect line, the key not written, `current()` not filling the field, no re-show after an action, the default stored as a value, the `_begin` guard removed: each turns tests red.

## 6. Docs touched
`Docs/MODULES/alerting/` README, 04, 05, 06, 08; `Docs/SPEC/SPEC-017`.

## Implementation notes (written when done)
The presenter is at 400 of 400 lines: any further group of the page needs its handlers moved out first (a group's request handlers into a helper owned by the presenter, as `SettingPanels` did for showing). `test_no_bots_is_said_in_words` asserted "no combo on the page"; it now asserts no bot-mode combo, which is what it meant, because the page has a combo for the heartbeat.

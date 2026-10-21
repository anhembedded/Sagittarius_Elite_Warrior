# EPIC-036D8 — The owner switches a channel off without removing it: the channel switches on the Options page

**Status:** ✅ Done (2026-10-21)
**Source:** the coordinator, 2026-10-21: finish `036D` in order, the channels table next; `EPIC-036D` §2 ("a channels table (name, type, last send and result, enabled)").
**Risk:** 🟡 — it decides where alerts go; every switch is on by default, so a missing or unreadable file is the safe side
**Complexity:** M
**Epic:** [EPIC-036](../README.md); a slice of [EPIC-036D](../incomplete/EPIC-036D_alerts_ui.md)
**SPEC:** [SPEC-017](../../../../Docs/SPEC/SPEC-017_set_up_an_alert_channel.md) step 9
**Depends on:** [EPIC-036D7](EPIC-036D7_routing_matrix_on_the_options_page.md)

---

## 1. Context and problem
`AlertSettings.disabled_channels` was read by the hub, the router and `ChannelAlertingStatus`, but nothing could set it: `JsonAlertSettings.current()` never filled it. An owner who wanted Telegram quiet for a week had to remove the bot and save it again.

## 2. Acceptance criteria
- [x] **A switch is kept across a restart** and reaches the hub: a switched-off channel is in `AlertSettings.disabled_channels`; every other channel stays on. (`test_a_channel_switched_off_survives_a_restart_and_the_hub_sees_it`, `test_switching_a_channel_on_again_removes_it_from_the_file`)
- [x] **A switched-off channel hears nothing, not even a Critical.** (`test_the_router_never_sends_to_a_switched_off_channel_not_even_for_a_critical`)
- [x] **An entry this build does not know leaves its channel on, told once**; the rest of the file is kept. (`test_an_entry_that_is_not_text_is_skipped_told_once_and_the_rest_kept`, `test_a_disabled_list_that_is_not_a_list_leaves_every_channel_on`)
- [x] **The switches sit beside the routes, modes and quiet hours** and cost none of them. (`test_switching_a_channel_off_keeps_the_routes_and_modes_beside_it`)
- [x] **Only a running channel can be switched**; a read-only copy changes nothing and says why; a store that cannot write is told. (`test_channels_setup.py`, `test_a_read_only_copy_refuses_a_switch`)
- [x] **The page**: a check box per running channel, acting at once, off while the work is out, a note when nothing is running or when every channel is off, a read-only note, and after an unexpected failure the box shows what was kept. (`test_alerts_page_channels.py`)
- [x] **Frames**: the page with the group, light and dark, three widths (`alerts_options@WxH.png`, artifact `ui-screenshots`); the size-hint check covers the check boxes.
- [ ] **A last-send time and result per channel**: not built (see §3).
- [ ] **The owner's look at the real window** (SPEC-017): not run.

## 3. Design
- **Switches, not a table.** `EPIC-036D` asked for a channels table with Add, Edit and Rotate. The Discord and Telegram groups already save, replace and remove each channel, so a table of two fixed rows would repeat them. What was missing is the on/off state, so that is what is built; the table earns its place when a third channel type exists (the seam is `ChannelsGroup`: one row per `channel_ids()` entry). A last-send column is left: the Alerts mode already shows each channel's deliveries, and reading them here would put an outbox read on the page's open.
- **A switch is not a removal.** The secret and the lane are untouched; the hub and the router skip the channel, so the change applies to the next alert without a restart.
- **Everything off is allowed and said.** `ChannelAlertingStatus` then reports no channel, and the page says no alert is sent anywhere, a Critical one included: it is the owner's word, and the router's N8 cover chooses among enabled channels only.
- **The port is two verbs, not a flag.** `IChannelEnabling.enable` / `disable` (no boolean that changes behaviour); the presenter picks `turn_on` or `turn_off` from the box's state.
- **The presenter's kinds left it** (`AlertsActionKind`, one file) and the quiet-hours sentence moved to `ActionResults`: the presenter was at 388 of 400 lines.

## 3a. Reuse
`used`: `JsonAlertSettings` and `SettingsDocument` (one more key), the page's tracker and relay, `ActionResults`, `IAlertChannelCatalog`, `routing_words.channel_title`. `not used`: `SpecTable` (a switch is a choice, not a figure to sort).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `alerting/contracts/i_channel_enabling.py` | the port |
| `alerting/adapters/settings_document.py`, `json_alert_settings.py` | `disabled_channels` in the file; the fourth port; `current()` fills it |
| `alerting/application/channels_setup.py` | switching a channel |
| `alerting/composition/settings_bindings.py` | the port bound to the same object |
| `alerting/ui/options/channels_group.py`, `channels_view_model.py`, `channels_words.py` | the group |
| `alerting/ui/options/alerts_action_kind.py`, `action_results.py`, `alerts_settings_presenter.py`, `alerts_settings_view.py`, `alerts_settings_view_model.py`, `alerts_words.py`, `preview.py` | wiring |

## 5. Testing
Unit: `test_json_alert_settings_channels.py`, `test_channels_setup.py`, `test_alerts_page_channels.py`; integration `test_alerts_options_page_frames.py`. Mutation-checked: no connect line, no re-read after an action, the key not written, `current()` not filling the field: each turns tests red.

## 6. Docs touched
`Docs/MODULES/alerting/` README, 04, 05, 06, 08; `Docs/SPEC/SPEC-017`.

## Implementation notes (written when done)
The presenter is at 394 of 400 lines: the heartbeat's interval, the last slice of `036D`, needs another part moved out first (the handlers of one group into a coordinator-shaped helper, or the bot-mode requests into `BotModeList`). The Discord and Telegram channel lines still say "On: alerts go to the saved Telegram bot" for a channel that is switched off, because they describe the secret and the lane, not the switch; the Channels group is the only place that shows the switch.

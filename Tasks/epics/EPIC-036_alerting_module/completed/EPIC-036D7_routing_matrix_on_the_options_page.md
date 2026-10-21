# EPIC-036D7 — The owner chooses who hears what: the routing matrix on the Options page

**Status:** ✅ Done (2026-10-21)
**Source:** the coordinator, 2026-10-21: *"options presenter split, routing matrix, then 036F's design record"*; design N1–N8 ("a routing matrix: alert group × channel with loudness", `EPIC-036D`).
**Risk:** 🟡 — it decides which alerts a phone rings for; the safe side is kept by the router, not by this page
**Complexity:** M
**Epic:** [EPIC-036](../README.md); a slice of [EPIC-036D](../incomplete/EPIC-036D_alerts_ui.md)
**SPEC:** [SPEC-017](../../../../Docs/SPEC/SPEC-017_set_up_an_alert_channel.md) step 8
**Depends on:** [EPIC-036D6](EPIC-036D6_quiet_hours_on_the_options_page.md)

---

## 1. Context and problem
`AlertRouter` already routes by a cell per `(AlertGroup, channel)` (`AlertSettings.loudness_for`), but `JsonAlertSettings.current()` never filled `routes`: the cells were always their defaults, and an owner who wanted routine messages off a phone had no way to say so.

## 2. Acceptance criteria
- [x] **A cell is kept across a restart** and reaches the hub: an Off cell sends nothing there, the others stay their defaults. (`test_a_route_survives_a_restart_and_the_hub_sees_it`, `test_a_cell_is_kept_and_reaches_the_hub`)
- [x] **A cell put back is no route**, not a copy of the default, so a later change of the defaults still reaches it. (`test_setting_a_cell_again_replaces_it_and_none_puts_it_back_to_its_default`, `test_a_cell_put_back_is_no_route_at_all`)
- [x] **An unknown entry is its default again, told once**, and the rest of the file is kept. (`test_a_route_this_build_does_not_know_is_its_default_told_once_and_the_rest_kept`, `test_one_good_route_beside_a_bad_one_is_kept`)
- [x] **Routes, bot modes and quiet hours are written together**; none costs another. (`test_routes_modes_and_quiet_hours_are_written_together_and_none_costs_another`)
- [x] **Only a running channel can be set**; a read-only copy changes nothing and says why; a store that cannot write is told. (`test_a_channel_this_run_does_not_have_is_refused_and_nothing_is_kept`, `test_a_read_only_copy_changes_nothing_and_says_so`, `test_a_store_that_cannot_write_is_told_not_reported_saved`)
- [x] **The page**: a row per kind of alert, a column per running channel, Default / Loud / Silent / Off in each cell, acting at once, off while the work is out, a note when nothing is running, a line saying a Critical still reaches two channels. (`test_alerts_page_routing.py`)
- [x] **Frames**: the page with the matrix, light and dark, three widths (`alerts_options@WxH.png`, artifact `ui-screenshots`).
- [ ] **The owner's look at the real window** (SPEC-017): not run.

## 3. Design
- **The rows are the groups the hub routes by** (`AlertGroup`), not a list written on the page; the page only gives them names. A new `AlertGroup` is a new row of `routing_words.GROUP_ROWS` (a test names every group).
- **Default is a choice, not an absence of one.** A cell with no route reads "Default"; choosing it again removes the route.
- **The matrix cannot silence a halt.** `AlertRouter.route` lifts a Critical to two channels from the enabled channels whose cell was Off (N8); the page says so under the matrix.
- **Columns are the running channels.** A route for a channel that is not running reaches nothing, so it is refused in words; a channel set up now appears after a restart.
- **A file's shape is a module of its own.** `settings_document.py` holds the document, its reading and its writing; `JsonAlertSettings` holds the lock, the commit and the ports (three ports on one object, so the hub's reads and the page's edits cannot disagree).
- **Two things left the page's presenter** (it was at 400 lines): the outcomes' sentences (`ActionResults`) and the failure box (`ActionResults.failed`).

## 3a. Reuse
`used`: `AlertRouter` / `AlertSettings.loudness_for` (the hub's own reading), `AlertGroup`, `Loudness`, `AlertRoute`, `JsonAlertSettings`, the page's tracker and relay. `not used`: a table (`SpecTable`): a cell is a choice, not a figure to sort.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `alerting/contracts/i_alert_routing.py` | the port |
| `alerting/adapters/settings_document.py`, `json_alert_settings.py` | the file's shape out; `routes` in; the third port |
| `alerting/application/routing_setup.py` | choosing a cell |
| `alerting/composition/settings_bindings.py` | the port bound to the same object |
| `alerting/ui/options/routing_matrix_group.py`, `routing_matrix_view_model.py`, `routing_words.py` | the group |
| `alerting/ui/options/action_results.py` | outcomes' words and the failure box, out of the presenter |
| `alerting/ui/options/alerts_settings_presenter.py`, `alerts_settings_view.py`, `alerts_settings_view_model.py`, `preview.py` | wiring |

## 5. Testing
Unit: `test_json_alert_settings.py`, `test_routing_setup.py`, `test_alerts_page_routing.py`; integration `test_alerts_options_page_frames.py`.

## 6. Docs touched
`Docs/MODULES/alerting/` README, 04, 05, 06, 08; `Docs/SPEC/SPEC-017`.

## Implementation notes (written when done)
The presenter is at 388 of 400 lines after two extractions; the next group of the page (the channels table) needs its own part moved out again.

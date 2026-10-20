# EPIC-036D2 — The owner can see what the app told them, and whether a channel is failing

**Status:** ✅ Done (2026-10-20)
**Source:** the coordinator, 2026-10-20: *"then 036D with preview frames (owner reviews frames; use EPIC-043's meaning table/tones, no new colours)"*; the owner's design of 2026-10-08 (N1–N8: "the owner can see what was sent, to which channel, and what failed").
**Risk:** 🟢 — a new read-only mode over the outbox; it changes no delivery
**Complexity:** M — a read model, one screen, one surface, one icon, frames
**Epic:** [EPIC-036](../README.md); the first slice of [EPIC-036D](../incomplete/EPIC-036D_alerts_ui.md)
**SPEC:** [SPEC-016](../../../../Docs/SPEC/SPEC-016_see_what_the_app_told_me.md)
**Depends on:** [EPIC-036A](EPIC-036A_alerting_core.md) (`IOutbox.history`), [EPIC-036C1](EPIC-036C1_telegram_alert_channel_and_token_migration.md) (a second channel to see)

---

## 1. Context and problem
A failure to deliver was a log line: the owner could not see what was sent, to which channel, or that one channel had stopped working (`EPIC-036` README, "Today" table). `IOutbox.history` already stores it all.

## 2. Acceptance criteria
- [x] **A read model** answers the newest alerts with, per alert, where it stands on each channel, and a health per channel (failing when its newest real delivery is failed, expired, or retrying after a failed try; pending, dropped and a wait the platform or the pacing asked for say nothing: `test_a_newer_alert_still_waiting_does_not_hide_a_failure` and its siblings, mutation-checked). (`test_outbox_alert_history.py`, over the real hub, worker and outbox)
- [x] **The Alerts mode** lists the alerts newest first in words (the time it was first raised, severity, about, alert with its count, delivery per channel); an alert that reached no channel says so. (`test_alerts_screen.py`)
- [x] **A channel line** names every channel working or failing with how many deliveries wait, and a **notice** appears only while a channel fails, naming it; it goes when the channel recovers. (`test_a_failing_channel_gets_a_notice_that_names_it`, `test_the_notice_goes_when_the_channel_recovers`)
- [x] **A severity filter** narrows the rows without a second read. (`test_the_filter_narrows_what_is_shown_without_reading_again`; mutation: `>=` to `>` turns it red)
- [x] **The read runs off the UI thread**, when the mode is shown and then every 15 s while it is visible, silently, one at a time, fenced, dropped after `shutdown()`, and a failed read keeps the list and says the exception's type only. (`test_a_read_in_flight_is_not_asked_twice`, `test_an_answer_after_shutdown_is_dropped`, `test_an_answer_for_a_read_that_is_no_longer_current_is_dropped` (mutation: fence removed turns it red), `test_a_failed_read_is_told_by_type_and_keeps_the_screen_alive`)
- [x] **Frames**: light and dark at 1024×700, 1366×768 and 1920×1080, not blank, no horizontal scroll, the notice shown whole. (`tests/integration/modules/alerting/test_alerts_frames.py`, an integration test so the `Rest` part keeps the pictures in the CI artifact `ui-screenshots`, named `alerts_preview…`)
- [x] **Wired**: the module contributes the screen, the shell declares the surface and the view's copy equals it, `IAlertHistory` is bound. (`test_alerting_module.py`; the workbench conformance suite passes with the mode present, except the `[True-1024x700]` case that fails on `master-warrior` too)
- [ ] **The owner's look at the real window** (SPEC-016 §8, "the user runs it"): not run.

## 3. Design
- **A read model, not the outbox record.** `IAlertHistory` hands the screen words-ready rows and a health per channel; the screen never learns `HistoryEntry`. `OutboxAlertHistory` is the one place that decides "failing". The seam is a port because the next consumer (the status-bar indicator of 036D) asks the same question.
- **A mode, not a dock.** The workbench has no seam for a contributed bottom dock; a screen is the contribution kind that exists (`ScreenContribution`). `alerting` owns the surface `alerts` (the view declares its copy, as the other modules do, a test holding them equal); the mode sits after Data and before Developer. HLD §11 and the View menu row are amended.
- **No colour of its own.** Severity and state are words. The shared meaning table and tones of `EPIC-043C` (#652) were not on `master-warrior`, so nothing is invented here; when they land, the severity cell takes their tone in one place (`history_table_model.py`).
- **Reads on the pool, every 15 s.** `IOutbox.history` queries SQLite; the presenter follows the Options page's pattern (`ActionOwnershipTracker`, `UiThreadRelay`, fenced, one at a time).
- **Names kept apart.** The duplication guard counts a method name two UI packages share; the screen's names are specific (`show_alert_history`, `take_alerts_read`, `show_history_note`) rather than extending a name another package already uses.
- **The mnemonic clash.** A new mode title takes the next free access key in mode order, which moved Backtest engine's key onto a View command's. The suite refused it; Remove from Watchlist's key moved to `&from`. The root, that a title can reach any command key, is not fixed here: it needs the commands' keys passed to the assignment (a main-window change), noted for the owner.

## 3a. Reuse
Checked `.claude/rules/capabilities.md`: `used SpecTable`, `RowTableModel`, `WorkbenchSurface`, `NoticeBar`, `plain_label`, `ActionOwnershipTracker`, `UiThreadRelay` (through `AlertsActionRelay`), `IThreadManager`; the screen contribution pattern of `database_screen`. `not used`: `INotifier` (a background poll must not pop a dialog), the colour tones (not yet on master).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `alerting/contracts/i_alert_history.py`, `alert_history_report.py` | the port and its records |
| `alerting/application/outbox_alert_history.py` | the read model over `IOutbox` and the channel catalog |
| `alerting/ui/history/*` | view, table model, presenter, words, screen contribution, preview |
| `alerting/module.py`, `composition/alerting_bindings.py` | contribute the screen; bind `IAlertHistory` |
| `shell/surfaces.py` | the `alerts` surface |
| `support/ui_kit/assets/icons/bell.svg`, `asset_validator_extension.py` | the mode's icon (Lucide `bell`) and its required-icon row |
| `trading/ui/market/market_commands.py` | Remove from Watchlist's access key |
| `Docs/HLD/11_desktop_workbench.md`, `Docs/SPEC/SPEC-016…`, `Docs/MODULES/alerting/*` | the mode, the journey, the design |

## 5. Testing
Unit: `test_outbox_alert_history.py`, `test_alerts_screen.py`, `test_alerting_module.py`; integration: `test_alerts_frames.py`. Architecture guards (incl. the duplication ratchet and the preview rule) and the workbench conformance suite run locally; the full gate is GitHub Actions'. Not run: the real window by the owner.

## 6. Docs touched
`Docs/MODULES/alerting/` README, 05-building-blocks, 06-runtime, 10-quality; `Docs/HLD/11_desktop_workbench.md` (the mode table and the View menu row); `Docs/SPEC/SPEC-016` and the SPEC index.

## Implementation notes (written when done)
The duplication ratchet went 32 → 39 on the first draft (seven method names another package also defined); renaming them brought it back to 32. The workbench suite failed on every dev-mode case when the mode was added (an access-key clash, above) and was brought back to master's single known failing case.

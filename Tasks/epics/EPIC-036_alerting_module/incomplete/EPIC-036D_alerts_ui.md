# EPIC-036D — Alerts UI: Options page, Alerts dock, status-bar indicator, per-bot mute

**Status:** 🔵 Planned — not started
**Source:** the owner's approval of the alerting design, 2026-10-08 (N4, N5), relayed by the coordinator session.
**Risk:** 🟢 — QtWidgets on existing seams; no change to delivery
**Complexity:** L — four surfaces and their previews
**Epic:** [EPIC-036](../README.md)
**SPEC:** none yet; a journey "set up an alert channel" is added by this task.
**Depends on:** [EPIC-036A](EPIC-036A_alerting_core.md) (settings, outbox history), [EPIC-036C](EPIC-036C_discord_channel_and_telegram_migration.md) (channels to configure and test).

---

## 1. Context and problem
Channels are configured by hand-editing the config; there is no test button, no history of what was sent and no sign in the app when a channel fails. Options pages are contributed through `IOptionsSection` (`src/core/contracts/i_options_section.py`); the bots list has a context menu. UI rules: QtWidgets only, OS theme, `configure_item_view`, async actions through the coordinator, a `preview.py` per package (`.claude/rules/ui-presentation-rule.md`, `async-ui-action-rule.md`).

## 2. Acceptance criteria
- [ ] **Tools → Options → Alerts** (an `IOptionsSection`): a **channels table** (name, type, last send and result, enabled) with Add…, Edit…, Remove and **Send test**; Add/Edit are a `QDialog` with a type, a name and a password-style secret field; on Edit an empty secret field keeps the stored secret; a secret is never shown back; a **Rotate webhook** action.
- [ ] **Routing matrix:** alert group × channel with loudness **Loud / Silent / Off**, N4 defaults pre-set; a short note that the platform accepting a message does not mean the owner read it, and that a stray message in the channel does not prove a bot has trouble.
- [ ] **Schedule:** heartbeat interval (default 6 h), quiet hours (off by default, CRITICAL still sent), and the **dead man's switch URL** field (off by default; the field is shown only if `EPIC-036E` has landed, otherwise this criterion is deferred in writing).
- [ ] **Apply/OK/Cancel/revert** follow the dialog's contract: nothing is saved by a page on its own; `is_dirty`, `validation_message` and `revert` are tested.
- [ ] **View → Alerts dock:** a history table (time, severity, subject, text, one column per channel with delivered / retrying / failed ×n / expired), a severity filter, **Retry failed**; a grouped alert shows its count on one row.
- [ ] **Status-bar indicator:** three states — off (no channel configured), ok, or "`<channel>` failing"; clicking it opens the dock; it follows `CHANNEL_FAILING` and its recovery.
- [ ] **Per bot:** an **Alerts: On / Critical only / Off** item in the bot's context menu; **Off asks for a confirmation** (N5); a muted-bell marker appears on the row of a bot whose alerts are not On.
- [ ] Every action that touches the network or the keyring (Send test, Retry failed, Rotate) runs off the UI thread through the async-action coordinator, with fencing and cooperative cancellation.
- [ ] Each package has a `preview.py` that renders its widgets headless; screenshots are attached to the PR.

## 3. Design
Model-View-Presenter with the project's presenters; the options page mirrors the existing Trading and Market data sections. The dock and the dialogs use `configure_item_view` and the shared widgets, and the alert groups come from the same code constants that `AlertHub` routes by, so the matrix cannot list a group the hub does not know. The dock reads the outbox's `history`; the indicator reads a small channel-health read model published by the worker. Verify the existing bots context-menu seam when the task starts.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/ui/options/` (new) | The Options page, the channel dialog, presenters |
| `src/modules/alerting/ui/dock/` (new) | The Alerts dock |
| `src/modules/alerting/ui/status/` (new) | The status-bar indicator |
| `src/modules/alerting/ui/*/preview.py` (new) | Previews |
| `src/modules/bots/ui/` (the bots list's context menu) | One generic hook for a contributed menu item and row marker, so `bots` still imports nothing from `alerting` |
| `src/shell/` (status bar, View menu) | The contributions registered |

## 5. Testing
Tier per `ci-rule.md` §2: unit for presenters and view-models, sanity/offscreen for the previews and the contribution wiring.
- `test_the_options_page_satisfies_ioptionssection`
- `test_the_page_is_dirty_only_after_an_edit_and_reverts_cleanly`
- `test_editing_a_channel_with_an_empty_secret_keeps_the_stored_secret`
- `test_a_secret_is_never_shown_back`
- `test_the_matrix_lists_exactly_the_hubs_alert_groups`
- `test_the_defaults_are_loud_for_critical_and_silent_for_warning`
- `test_send_test_runs_off_the_ui_thread_and_shows_the_guidance`
- `test_the_dock_shows_the_delivery_status_per_channel`
- `test_retry_failed_requeues_only_failed_deliveries`
- `test_the_indicator_is_off_ok_or_names_the_failing_channel`
- `test_turning_a_bot_off_asks_for_confirmation`
- `test_a_muted_bot_row_shows_the_bell`
- `test_bots_still_imports_nothing_from_alerting` (boundary guard)
- previews: channels table, matrix, dock with failures, indicator in three states, muted row — screenshots in the PR

Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: `test_the_options_page_satisfies_ioptionssection`, run red.

# EPIC-036D5 — The owner can send failed deliveries again, and a severity reads by tone

**Status:** ✅ Done (2026-10-21)
**Source:** the coordinator, 2026-10-21: *"Retry failed + severity tone next, as you propose"*; design N1–N8 ("Retry failed", `EPIC-036D`); the tone after `EPIC-043C` (#652).
**Risk:** 🟡 — it writes the outbox from the UI (the owner's action) and a failed delivery goes out again
**Complexity:** S
**Epic:** [EPIC-036](../README.md); the fourth slice of [EPIC-036D](../incomplete/EPIC-036D_alerts_ui.md)
**SPEC:** [SPEC-016](../../../../Docs/SPEC/SPEC-016_see_what_the_app_told_me.md) steps 8 and 9
**Depends on:** [EPIC-036D2](EPIC-036D2_alerts_screen_history_and_channel_status.md), `EPIC-043C`

---

## 1. Context and problem
A delivery that gave up (`FAILED`) stays failed after its cause is fixed (a webhook saved again, a bot added to the chat): the owner had no way to send it again. And the Alerts table showed severity only as a word.

## 2. Acceptance criteria
- [x] **Retry failed requeues what gave up.** A `FAILED` delivery of an alert inside the expiry goes back to `PENDING`, attempts counted afresh, and is delivered by the lane. (`test_a_refused_delivery_is_sent_after_retry_failed_once_the_channel_works`, `test_requeue_failed_puts_a_failed_delivery_back_due_now_with_fresh_attempts`)
- [x] **Nothing else changes.** Sent, expired and older-than-expiry deliveries are left; with none failed the answer is "nothing to retry". (`test_requeue_failed_leaves_sent_expired_and_older_than_the_cutoff_alone`, `test_a_failure_older_than_the_expiry_is_not_sent_late`, `test_with_nothing_failed_it_says_nothing_to_retry`)
- [x] **Off the UI thread, fenced.** The button greys while the work is out; a second click does nothing; a stale answer is dropped; a failure is told by type name only. (`test_the_button_is_off_while_the_work_is_out_and_a_second_click_does_nothing`, `test_a_failed_retry_is_told_by_type_and_leaves_the_screen_usable`)
- [x] **A read-only copy cannot retry.** The button is off and says why. (`test_a_copy_that_may_not_write_cannot_retry`)
- [x] **The answer stays on screen** over the read that follows it. (`test_the_answer_stays_on_screen_over_the_read_that_follows`)
- [x] **Severity by tone and word.** Critical is a loss tone, Warning a caution, Info plain; the word is always there. (`test_alerts_severity_tone.py`, `test_alerts_frames.py`)
- [x] **Frames**: the screen with the button and the tones, light and dark, three widths (`alerts_preview@WxH.png`, artifact `ui-screenshots`).
- [ ] **The owner's look at the real window** (SPEC-016 §8): not run.

## 3. Design
- **A port of its own.** `IDeliveryRequeue`, not a method of `IOutbox`: the outbox port is the hub's and the lanes' and `SqliteOutbox` is at the public-method ceiling (`PLR0904`). The adapter opens a connection for the one call (the file is WAL; the write waits for the outbox's short transaction).
- **No wake needed.** The lane polls every `LANE_POLL_SECONDS`; the requeued deliveries are due now, so they go out at the next look.
- **Only what is inside the expiry.** An alert older than `DeliveryPolicy.expiry` is not sent late (N2).
- **The tone is the shared mechanism** (`RowTableModel._tone`, `Tone`), no colour written here.

## 3a. Reuse
`used`: `RowTableModel._tone` and `Tone` (#652), `AlertsActionRelay`, `ActionOwnershipTracker`, `IInstanceAccess`, `DeliveryPolicy.expiry`. `not used`: `IOutbox` (kept narrow).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `alerting/contracts/i_delivery_requeue.py`, `alerting/adapters/sqlite_delivery_requeue.py` | the port and its SQLite adapter |
| `alerting/application/retry_failed_deliveries.py` | the use case |
| `alerting/composition/history_bindings.py` | the history and retry bindings (split from `alerting_bindings.py`, at the ceiling) |
| `alerting/ui/history/alerts_presenter.py`, `alerts_view.py`, `history_words.py` | the button, the action, the words |
| `alerting/ui/history/history_table_model.py` | `_tone` |

## 5. Testing
Unit: `test_sqlite_delivery_requeue.py`, `test_retry_failed_deliveries.py`, `test_alerts_retry_failed.py`, `test_alerts_severity_tone.py`; integration `test_alerts_frames.py`.

## 6. Docs touched
`Docs/MODULES/alerting/` README, 05, 06, 10; `Docs/SPEC/SPEC-016`.

## Implementation notes (written when done)
The first cut put `requeue_failed` on `IOutbox` and failed two ratchets (`PLR0904` on `SqliteOutbox`, the god-file ceiling on `alerting_bindings.py`); the port of its own and `history_bindings.py` are the repair, not a baseline entry.

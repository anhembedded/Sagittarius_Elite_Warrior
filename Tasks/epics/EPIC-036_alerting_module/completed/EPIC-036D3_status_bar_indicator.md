# EPIC-036D3 — The window says in every mode whether alerts are getting through

**Status:** ✅ Done (2026-10-21)
**Source:** the coordinator, 2026-10-20: *"continue 036D's next slice (status-bar indicator)"*; design N1–N8 ("a status-bar indicator", `EPIC-036D`).
**Risk:** 🟢 — a status-bar widget and a background read of the outbox; no change to delivery
**Complexity:** S — the seam (`IStatusSource`) and the read model (`IAlertHistory`) existed
**Epic:** [EPIC-036](../README.md); the second slice of [EPIC-036D](../incomplete/EPIC-036D_alerts_ui.md)
**SPEC:** [SPEC-016](../../../../Docs/SPEC/SPEC-016_see_what_the_app_told_me.md) step 7
**Depends on:** [EPIC-036D2](EPIC-036D2_alerts_screen_history_and_channel_status.md)

---

## 1. Context and problem
`EPIC-036D2` shows whether a channel fails, but only inside the Alerts mode. An owner in the Trade mode would not see a channel go dark.

## 2. Acceptance criteria
- [x] **The view offers one status widget** (`IStatusSource`), hidden until the first read. (`test_the_view_offers_its_indicator_to_the_window`, `test_the_indicator_is_not_shown_until_something_has_been_read`)
- [x] **Three states in words**: `Alerts: ok`, `Alerts: no channel`, `Alerts: <channel> failing`; a failing channel also has a warning icon (colour never alone). (`test_it_says_ok…`, `…off…`, `test_it_names_a_failing_channel_in_words_and_with_an_icon`)
- [x] **A click shows the Alerts mode** through the window's navigation service, resolved at the click. (`test_clicking_the_indicator_shows_the_alerts_mode`)
- [x] **It is fed in every mode**: a background read after 5 s and every 15 s, whether or not the mode is visible, with 1 alert while hidden and 500 while shown; nothing is read at build. (`test_a_hidden_mode_is_still_read_for_the_indicator_but_for_one_alert_only`, `test_nothing_is_read_at_build_and_showing_the_mode_reads_the_whole_list`)
- [x] **Frames**: the indicator in a status bar with a failing channel, light and dark, three widths. (`test_alerts_frames.py`, artifact `ui-screenshots`, `alerts_indicator@WxH.png`)
- [ ] **The owner's look at the real window** (SPEC-016 §8): not run.

## 3. Design
- **The existing seam.** `IStatusSource.status_widgets` is how Data and Market put state in the status bar (`EPIC-033H`); no shell change was needed. (The `036D` plan said a shell hook would be needed: it was not.)
- **Fed by the one presenter.** The indicator and the table are two views of one read, so the presenter that owns the read also drives the indicator; a second reader would query the outbox twice.
- **Nothing read at build.** `test_the_window_shuts_down_within_budget` fails when a read at build starts pool threads (found in `EPIC-036D2`). The timers do not touch the pool until their first tick, 5 s after start, which no start-up test reaches.
- **Hidden reads are small, and health is not windowed.** Review round 1 found that a retrying head with 50+ alerts queued behind it fell out of a 50-alert window and the indicator said `ok`. `OutboxAlertHistory` now asks `IOutbox.latest_real_delivery` (the channel's newest sent/failed/expired/retrying delivery, any age), so a hidden read is one alert and updates the indicator only. A failed read shows `Alerts: unknown`, logged once per run of failures.
- **Words and an icon, no colour.** `NoticeBar`'s platform warning icon, as the notice of `EPIC-036D2`.

## 3a. Reuse
`used IStatusSource` (the seam), `INavigationService`, `IAlertHistory` and the presenter of `EPIC-036D2`. `not used`: `HealthFeed` (a once-per-refresh snapshot of the engine's health, not a poll of the outbox).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `alerting/ui/history/alerts_view.py` | the indicator and `status_widgets`; `indicator_clicked` |
| `alerting/ui/history/alerts_presenter.py` | timers, `_poll`, the click; `HEALTH_LIMIT`, `FIRST_READ_MS` |
| `alerting/ui/history/history_words.py` | `indicator_text` and its words |
| `Docs/…` | SPEC-016, HLD §11.2.2, the module design |

## 5. Testing
Unit `test_alerts_indicator.py`, `test_alerts_screen.py`; integration `test_alerts_frames.py`. Architecture guards, sanity and the presentation integration tests pass locally except `[True-1024x700]` (fails on `master-warrior` too) and a socket test of this container.

## 6. Docs touched
`Docs/MODULES/alerting/` README, 05, 06, 10; `Docs/HLD/11_desktop_workbench.md` §11.2.2; `Docs/SPEC/SPEC-016`.

## Implementation notes (written when done)
The new method names (`_poll`, `indicator_text`) were checked against the duplication ratchet; it stays at its baseline.

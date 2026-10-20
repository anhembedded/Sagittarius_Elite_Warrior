# EPIC-036C2 — A burst of messages is spread under the platform's rate limit, and a webhook rotation is proven

**Status:** ✅ Done (2026-10-20) — built and proven by unit tests over the real hub, outbox and worker pass; the owner's first real burst on the VPS is still to be seen
**Source:** the coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`, 2026-10-20: *"do 036C2 next ... Pacing matters most: the per-fill messages of PRO-015 can burst"*
**Risk:** 🟢 — a wrapper around a channel and a shorter lane sleep; no order, stop or close path, no new setting or dependency
**Complexity:** S
**Epic:** [EPIC-036](../README.md); split from [EPIC-036C](../incomplete/EPIC-036C_discord_channel_and_telegram_migration.md), which keeps the Discord embed (a decision, §3) and the Options page's Telegram fields (moved to `036D`, §3)
**SPEC:** none yet
**Design:** [`Docs/MODULES/alerting/`](../../../../Docs/MODULES/alerting/README.md)
**Depends on:** [EPIC-036G](EPIC-036G_walking_skeleton_halt_to_discord.md), [EPIC-036A](EPIC-036A_alerting_core.md)

---

## 1. Context and problem
Until now a channel found a platform's rate limit by being answered 429 (`discord_answer.py`). Research 036 §1 records that a client that keeps hitting 429 is banned by IP, which loses every alert; and the per-fill messages (`BOT-189`, bounded to 25 per channel by `FillBacklog`) plus a grouped alert, a heartbeat and a summary can arrive together.

## 2. Acceptance criteria
- [x] **A channel keeps itself under its limit**: `PacedChannel` wraps a channel with a `SendWindow`; a send over `PacingPolicy` is answered `retry_later(wait)` without calling the platform, and the wait is exactly until the oldest send leaves the window. (`test_a_send_over_the_limit_is_asked_to_wait_and_the_platform_is_not_called`, `test_the_window_admits_its_limit_and_names_the_wait_for_the_next`)
- [x] **Nothing is lost and no attempt is used**: thirty messages published at one instant all reach the channel, never more than four in any two seconds, each with one real try. (`test_a_burst_of_fill_messages_is_spread_under_the_limit_and_none_is_lost`; red when the window's comparison is off by one)
- [x] **A failed try still counts** against the window; the platform's own answer is passed on unchanged. (`test_a_try_the_platform_answered_with_a_failure_still_counts_against_the_limit`, `test_the_answer_of_the_platform_is_passed_on_unchanged`)
- [x] **The lane does not stretch a short wait to its poll interval**: it sleeps `min(poll, pause_remaining)` (at least 50 ms). (`test_the_lane_is_told_how_long_the_channel_still_waits`)
- [x] **Wired**: the Discord channel the descriptor builds is paced (`test_a_stored_webhook_puts_discord_in_the_catalog`). Telegram's descriptor is wrapped the same way (`TELEGRAM_PACING`) in the branch that holds it (`EPIC-036C1`).
- [x] **Rotation is proven**: Save over a stored webhook replaces it, the state shows only the new token's last four characters, no log line holds either URL, and a rotation to a value that is not a webhook keeps the old one. (`test_rotating_the_webhook_replaces_the_stored_secret_and_shows_nothing`, `test_a_rotation_to_something_that_is_not_a_webhook_keeps_the_old_one`)
- [ ] **A real burst on the VPS** (a grid with many fills): not run.

## 3. Design
`PacedChannel` is a decorator over `IAlertChannel` rather than a rule inside each channel, so every channel (a third one too) is paced by one line in its descriptor. The wait is returned as a 429 would be, which the worker already handles without an attempt; the one new mechanism is the lane's shorter sleep.

**The figures are constants, not measurements** (the owner may change them): Discord 4 messages per 2 s (a margin under the documented about 5 per 2 s per webhook), Telegram 1 per second. Reading the platform's own `X-RateLimit-*` headers is the named extension case of `PacedChannel`.

**Two items of the 036C list are not built here, and why**
- **The Discord embed (a decision for the owner).** An embed gives a colour bar, but the push notification on a phone shows the message `content`, not the embed: today the content carries the severity mark, the title, the subject and the reason, which is what the owner reads on the lock screen. Moving the detail into an embed would lose it there; duplicating it would double the text. The severity marks (red, orange and blue circles) already give the colour at a glance, and the 2000-character cut is handled by the heartbeat's own budget. Recommendation: leave Discord as it is unless the owner wants the bar badly enough to read the reason one tap later.
- **The Options page's Telegram fields and Rotate button** move to `036D`, whose channels table will hold every channel's secret fields: building them here would be rebuilt there.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/adapters/paced_channel.py` (new) | `PacedChannel`, `SendWindow` |
| `src/modules/alerting/domain/alert_policies.py` | `PacingPolicy`, `DISCORD_PACING`, `TELEGRAM_PACING` |
| `src/modules/alerting/application/channel_delivery.py` | `pause_remaining` |
| `src/modules/alerting/adapters/threaded_delivery_host.py` | The lane's `_sleep_of` |
| `src/modules/alerting/composition/channel_bindings.py` | The Discord descriptor wraps its channel |
| `tests/unit/modules/alerting/world.py` | `build_rig(channel_map=...)` |

## 5. Testing
`test_paced_channel.py`, `test_failover_and_waits.py` (the lane's wait), `test_channel_bindings.py`, `test_discord_webhook_setup.py` (rotation).

## Implementation notes (written when done)
2026-10-20. Branch `claude/epic-036c2-pacing-and-embed`, from `master-warrior` after `036B`.

- The window counts every try that reached the platform, whatever its answer; a refused try (pacing) is not counted.
- Branched before `036C1` (#654) merged, so the Telegram descriptor is not touched here; its wrap is one line to add on merge (`PacedChannel(..., TELEGRAM_PACING)`).

Not run: a real burst on Discord.

## Resume
Done. The owner's decision: the Discord embed (§3). The next task is `036D`.

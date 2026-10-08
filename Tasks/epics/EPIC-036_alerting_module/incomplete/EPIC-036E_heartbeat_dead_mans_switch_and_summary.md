# EPIC-036E — Heartbeat, dead man's switch and daily summary: silence is itself an alert

**Status:** 🔵 Planned — not started; waits for [`EPIC-035W`](../../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md), which the owner asked not to start yet
**Source:** the owner's approval of the alerting design, 2026-10-08 (N4, N7), relayed by the coordinator session. Absorbs the heartbeat criterion of [`EPIC-035K`](../../EPIC-035_spot_grid_unattended_safety/cancelled/EPIC-035K_alerts_reach_a_user_who_is_away.md) ("the heartbeat's absence is itself the alert").
**Risk:** 🟡 — a timer on the alert path and a new outbound ping to a third-party service
**Complexity:** M
**Epic:** [EPIC-036](../README.md)
**SPEC:** none yet.
**Design:** [`DESIGN_2026-10-08_alerting_module.md`](../DESIGN_2026-10-08_alerting_module.md) (the design of record; the owner's page is a secondary reference). **Research:** [`RESEARCH_2026-10-08_alerting_lessons.md`](../RESEARCH_2026-10-08_alerting_lessons.md) §10.
**Depends on:** [EPIC-036A](EPIC-036A_alerting_core.md), [EPIC-036C](EPIC-036C_discord_channel_and_telegram_migration.md); [EPIC-035W](../../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md) for the health snapshot.

---

## 1. Context and problem
A monitoring system that dies goes quiet, and the app cannot report that it is dead. A heartbeat message helps only if the owner notices its absence; the standard answer is a **dead man's switch**: an external service expects a regular signal and alerts the owner when it stops. `EPIC-035W` defines one immutable health snapshot per bot (feed age, stream state, last reconcile, open orders); the heartbeat must read that same snapshot, so the screen and the message cannot disagree. Verify the snapshot's shape when the task starts.

## 2. Acceptance criteria
- [ ] **`HeartbeatService`** raises a `HEARTBEAT` (INFO) alert every `heartbeat_every` (default **6 h**, N4), listing each bot's state, the age of its last price tick, its user-stream state and its last reconcile, read from the `EPIC-035W` snapshot — **not** recomputed.
- [ ] **Daily summary:** a `DAILY_SUMMARY` that releases the WARNINGs held during quiet hours as one message when the quiet period ends; with no quiet hours configured, no summary is sent.
- [ ] **Dead man's switch (N7):** a ping adapter calls an external URL (healthchecks.io or one the owner picks) every 5 minutes while the app is healthy; **off by default**; the URL is a secret held in the keyring, never logged, shown or kept in config; an unreachable service never blocks or delays an alert, and its failure is shown as a channel failure.
- [ ] The ping reflects the app being truly alive: it is sent from the worker's own loop, not from a separate thread that would keep pinging while delivery is wedged; a wedged worker stops the ping.
- [ ] The heartbeat is an INFO alert and obeys the same routing, loudness and quiet hours as any other; it is never mistaken for a recovery.
- [ ] Without `EPIC-035W` the task does not invent a second snapshot: the heartbeat ships only after it, or ships with the ping and the summary and adds the heartbeat body when the snapshot exists, in writing.

## 3. Design
A dead man's switch (a *watchdog* heartbeat to an independent monitor), implemented as one more outbound adapter that is not an `IAlertChannel` (it carries no alert, only liveness); a timer driven by the injected clock/ticker of `EPIC-035A`. The snapshot is a read-only query port in `bots/contracts` (owned by 035W); `alerting` depends on it, not on a presenter. The ping cadence is a named constant.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/application/heartbeat_service.py` (new) | The periodic heartbeat and the summary release |
| `src/modules/alerting/adapters/dead_mans_switch_pinger.py` (new) | The ping adapter and its secret |
| `src/modules/alerting/composition/` | Wiring, off by default |
| `src/modules/alerting/ui/options/` | The URL field of `EPIC-036D` is enabled |

## 5. Testing
Tier per `ci-rule.md` §2: unit with a fake clock, a fake transport and a fake snapshot.
- `test_a_heartbeat_fires_on_the_interval` (fake clock)
- `test_the_heartbeat_and_the_screen_read_one_snapshot`
- `test_the_heartbeat_lists_each_bots_state_and_feed_age`
- `test_quiet_hours_hold_warnings_and_release_one_summary`
- `test_no_summary_without_quiet_hours`
- `test_the_dead_mans_switch_is_off_by_default`
- `test_the_ping_is_sent_every_five_minutes_while_the_worker_is_alive`
- `test_a_wedged_worker_stops_the_ping`
- `test_an_unreachable_ping_service_never_delays_an_alert`
- `test_the_ping_url_never_appears_in_a_log_or_error` (red-flag test)
- manual: kill the app and confirm the external service alerts the owner; recorded in the task

Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. Blocked on `EPIC-035W` for the heartbeat body only. First action: `test_a_heartbeat_fires_on_the_interval`, run red.

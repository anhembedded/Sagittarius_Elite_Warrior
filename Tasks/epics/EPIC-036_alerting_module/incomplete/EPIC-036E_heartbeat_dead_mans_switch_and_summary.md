# EPIC-036E — Heartbeat and daily summary: the owner hears from the bots on a schedule

**Status:** 🔵 Planned — not started; the dead man's switch was split off as [`EPIC-036E1`](../completed/EPIC-036E1_dead_mans_switch.md) and is done (2026-10-20); the heartbeat and the summary wait for [`EPIC-035W`](../../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md), which the owner asked not to start yet
**Source:** the owner's approval of the alerting design, 2026-10-08 (N4, N7), relayed by the coordinator session. Absorbs the heartbeat criterion of [`EPIC-035K`](../../EPIC-035_spot_grid_unattended_safety/cancelled/EPIC-035K_alerts_reach_a_user_who_is_away.md) ("the heartbeat's absence is itself the alert").
**Risk:** 🟡 — a timer on the alert path
**Complexity:** M
**Epic:** [EPIC-036](../README.md)
**SPEC:** none yet.
**Design:** [`Docs/MODULES/alerting/`](../../../../Docs/MODULES/alerting/README.md) (the module's current design, since 2026-10-15); the design approved on 2026-10-08 is kept as the record in [`DESIGN_2026-10-08_alerting_module.md`](../DESIGN_2026-10-08_alerting_module.md). **Research:** [`RESEARCH_2026-10-08_alerting_lessons.md`](../RESEARCH_2026-10-08_alerting_lessons.md) §10.
**Depends on:** [EPIC-036E1](../completed/EPIC-036E1_dead_mans_switch.md) (the switch, done), [EPIC-036A](../completed/EPIC-036A_alerting_core.md), [EPIC-036G](EPIC-036G_walking_skeleton_halt_to_discord.md), [EPIC-036C](EPIC-036C_discord_channel_and_telegram_migration.md); [EPIC-035W](../../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md) for the health snapshot.

> **Note, 2026-10-15 — re-sequenced behind the walking skeleton** ([decision D2, D5](../DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md)). After `EPIC-036G` a halt reaches Discord, but an app that dies is still silent: this task is what the generated unit file's header then still names as missing. The dead man's switch URL is a secret and follows the skeleton's route (D3): a systemd credential on a headless host.

---

> **Note, 2026-10-20 — the switch is split off** ([decision](../DECISION_2026-10-20_dead_mans_switch.md) D1). The dead man's switch needs no health content, so [`EPIC-036E1`](../completed/EPIC-036E1_dead_mans_switch.md) built it without `EPIC-035W`. Its acceptance criteria below that mention the ping are done there; this task keeps the heartbeat and the summary. The file keeps its name so links stay valid.

## 1. Context and problem
A monitoring system that dies goes quiet, and the app cannot report that it is dead. A heartbeat message helps only if the owner notices its absence; the standard answer is a **dead man's switch**: an external service expects a regular signal and alerts the owner when it stops. `EPIC-035W` defines one immutable health snapshot per bot (feed age, stream state, last reconcile, open orders); the heartbeat must read that same snapshot, so the screen and the message cannot disagree. Verify the snapshot's shape when the task starts.

## 2. Acceptance criteria
- [ ] **`HeartbeatService`** raises a `HEARTBEAT` (INFO) alert every `heartbeat_every` (default **6 h**, N4), listing each bot's state, the age of its last price tick, its user-stream state and its last reconcile, read from the `EPIC-035W` snapshot — **not** recomputed.
- [ ] **Daily summary:** a `DAILY_SUMMARY` that releases the WARNINGs held during quiet hours as one message when the quiet period ends; with no quiet hours configured, no summary is sent.
- [x] ~~Dead man's switch (N7)~~ and ~~the ping reflects the app being truly alive~~ — done in [`EPIC-036E1`](../completed/EPIC-036E1_dead_mans_switch.md).
- [ ] The heartbeat is an INFO alert and obeys the same routing, loudness and quiet hours as any other; it is never mistaken for a recovery.
- [ ] The task does not invent a second snapshot: the heartbeat ships after `EPIC-035W`, reading its snapshot.

## 3. Design
The dead man's switch is built (`EPIC-036E1`). The heartbeat is a timer driven by the injected clock/ticker of `EPIC-035A` that raises an INFO alert. The snapshot is a read-only query port in `bots/contracts` (owned by 035W); `alerting` depends on it, not on a presenter. The ping cadence is a named constant.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/application/heartbeat_service.py` (new) | The periodic heartbeat and the summary release |
| `src/modules/alerting/composition/` | Wiring |
| `src/modules/alerting/ui/options/` | The heartbeat interval, with `EPIC-036D` |

## 5. Testing
Tier per `ci-rule.md` §2: unit with a fake clock, a fake transport and a fake snapshot.
- `test_a_heartbeat_fires_on_the_interval` (fake clock)
- `test_the_heartbeat_and_the_screen_read_one_snapshot`
- `test_the_heartbeat_lists_each_bots_state_and_feed_age`
- `test_quiet_hours_hold_warnings_and_release_one_summary`
- `test_no_summary_without_quiet_hours`

Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. Blocked on `EPIC-035W` for the heartbeat body. First action: `test_a_heartbeat_fires_on_the_interval`, run red.

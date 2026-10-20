# EPIC-036E — Heartbeat and daily summary: the owner hears from the bots on a schedule

**Status:** ✅ Done (2026-10-20) — the heartbeat and the daily summary; the dead man's switch was split off as [`EPIC-036E1`](EPIC-036E1_dead_mans_switch.md) and done earlier. The per-bot health inside the heartbeat waits for [`EPIC-035W`](../../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md), which the owner asked not to start
**Source:** the owner's approval of the alerting design, 2026-10-08 (N4, N7), relayed by the coordinator session. Absorbs the heartbeat criterion of [`EPIC-035K`](../../EPIC-035_spot_grid_unattended_safety/cancelled/EPIC-035K_alerts_reach_a_user_who_is_away.md) ("the heartbeat's absence is itself the alert").
**Board:** A silent INFO heartbeat every 6 h and one daily summary after 01:00 UTC reach the alert channels from the bots' status report; neither `036C` nor `035W` was needed to build them.
**Risk:** 🟡 — a timer on the alert path
**Complexity:** M
**Epic:** [EPIC-036](../README.md)
**SPEC:** none yet.
**Design:** [`Docs/MODULES/alerting/`](../../../../Docs/MODULES/alerting/README.md) (the module's current design, since 2026-10-15); the design approved on 2026-10-08 is kept as the record in [`DESIGN_2026-10-08_alerting_module.md`](../DESIGN_2026-10-08_alerting_module.md). **Research:** [`RESEARCH_2026-10-08_alerting_lessons.md`](../RESEARCH_2026-10-08_alerting_lessons.md) §10.
**Depends on:** [EPIC-036E1](../completed/EPIC-036E1_dead_mans_switch.md) (the switch, done), [EPIC-036A](../completed/EPIC-036A_alerting_core.md), [EPIC-036G](EPIC-036G_walking_skeleton_halt_to_discord.md), [EPIC-036C](../incomplete/EPIC-036C_discord_channel_and_telegram_migration.md); [EPIC-035W](../../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md) for the health snapshot.

> **Note, 2026-10-15 — re-sequenced behind the walking skeleton** ([decision D2, D5](../DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md)). After `EPIC-036G` a halt reaches Discord, but an app that dies is still silent: this task is what the generated unit file's header then still names as missing. The dead man's switch URL is a secret and follows the skeleton's route (D3): a systemd credential on a headless host.

---

> **Note, 2026-10-20 — the switch is split off** ([decision](../DECISION_2026-10-20_dead_mans_switch.md) D1). The dead man's switch needs no health content, so [`EPIC-036E1`](../completed/EPIC-036E1_dead_mans_switch.md) built it without `EPIC-035W`. Its acceptance criteria below that mention the ping are done there; this task keeps the heartbeat and the summary. The file keeps its name so links stay valid.

## 1. Context and problem
A monitoring system that dies goes quiet, and the app cannot report that it is dead. A heartbeat message helps only if the owner notices its absence; the standard answer is a **dead man's switch**: an external service expects a regular signal and alerts the owner when it stops. `EPIC-035W` defines one immutable health snapshot per bot (feed age, stream state, last reconcile, open orders); the heartbeat must read that same snapshot, so the screen and the message cannot disagree. Verify the snapshot's shape when the task starts.

## 2. Acceptance criteria
- [x] **`HeartbeatService`** raises a `HEARTBEAT` (INFO) alert every `heartbeat_every` (default **6 h**, N4), listing each active bot's state, reason and resting orders from the bots' status report, and the report's `health` snapshot (feed age, stream state, last reconcile) **verbatim** once `EPIC-035W` fills it — never recomputed. Until then those figures are absent from the message, not invented.
- [x] **Daily summary:** the release of the WARNINGs held during quiet hours as one message already existed (`QuietHoursHold`, `EPIC-036A`). This task adds what the owner asked for in words — *one daily summary in Discord*: a `DAILY_SUMMARY` once a day after 01:00 UTC with the bots by state, each run's earnings as its record has them and the alerts of the last 24 h by kind, whether or not quiet hours are configured. Superseded wording: the original criterion tied the summary to quiet hours only; the owner's request of 2026-10-20 is the reason it does not.
- [x] ~~Dead man's switch (N7)~~ and ~~the ping reflects the app being truly alive~~ — done in [`EPIC-036E1`](../completed/EPIC-036E1_dead_mans_switch.md).
- [x] The heartbeat is an INFO alert and obeys the same routing, loudness and quiet hours as any other; it is never mistaken for a recovery (`test_the_heartbeat_is_a_silent_info_message_on_every_channel`, `test_a_heartbeat_inside_quiet_hours_waits_with_the_other_info_alerts`).
- [x] The task does not invent a second snapshot. Decision recorded: it does not wait for `EPIC-035W` either, because `EPIC-038C`'s `BotStatusReport` is already the one read model the heartbeat is documented to read and reserves the `health` slot 035W fills; the heartbeat prints it unchanged.

## 3. Design
The dead man's switch is built (`EPIC-036E1`). The heartbeat is a timer driven by the injected clock/ticker of `EPIC-035A` that raises an INFO alert. The snapshot is a read-only query port in `bots/contracts` (owned by 035W); `alerting` depends on it, not on a presenter. The ping cadence is a named constant.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/application/heartbeat_service.py` (new) | The periodic heartbeat and the summary release |
| `src/modules/alerting/composition/` | Wiring |
| `src/modules/alerting/ui/options/` | The heartbeat interval, with `EPIC-036D` |

## 5. Testing
Unit over the real hub and outbox with a fake clock and a fake report (`tests/unit/modules/alerting/application/test_heartbeat_service.py`), plus one booted-app test (`tests/integration/modules/alerting/test_the_composed_app_sends_its_heartbeat.py`):
- a heartbeat at the first tick, then only each interval (the boundary tested at exactly `heartbeat_every`)
- a restart inside the interval sends no second one
- each active bot's state, reason and resting orders; the `health` slot verbatim; no figure invented without it; "No bot is configured"; an unreadable report still sends a heartbeat saying so; a tick never raises
- silent INFO on every channel; held with the other INFO alerts inside quiet hours
- the summary once a day after its time, never before, never twice; an app started after the time sends none that day; the bots by state, earnings and the alerts of the last day; its key (the date) does not meet the quiet-hours digest's
- the booted app sends a heartbeat to the stored Discord webhook (red when the housekeeping call is removed)

## Implementation notes (written when done)
2026-10-20. Branch `claude/epic-036e-heartbeat-and-daily-summary`.

- **Dependencies, checked against the tree first.** `036C` (Telegram, embeds, migration) is not in the heartbeat's path: Discord delivers plain text since `036G`. `035W` is not needed to build it: the status report is the model this task was written to read, with a `health` slot reserved. So both are skipped here, not built.
- **Where it runs.** `HeartbeatService.tick` (`alerting/application/heartbeat_service.py`) is called once a second by the housekeeping thread before the hub's flush (`alerting_bindings.py` → `_housekeeping_of`), so a failing flush cannot hold a heartbeat back and a tick never raises.
- **Survives a restart** by reading the newest 500 alerts of the outbox; on a day busier than that a restart may repeat one heartbeat (recorded in the class docstring).
- **Chosen defaults the owner may veto:** the summary hour is **01:00 UTC** (`HeartbeatPolicy.summary_at`; 08:00 in UTC+7), and a summary the app missed is not sent late. The heartbeat period is N4's 6 h. A UI for both belongs to `036D`.
- **What the message contains** is in `heartbeat_text.py`: counts by state, then each active bot's line; the summary adds earnings (`grid_profit`, cycles, `total_pnl` as the record has them, "not priced yet" when `None`) and the alerts of the last 24 h by kind, heartbeats and summaries excluded.
- The traceback or error text is never in these messages; an unreadable report names only the error's type.

Not run: a heartbeat and a summary received in the owner's Discord from the VPS.

## Resume
Done. The owner's check on the VPS: after a restart with the webhook stored, one "Heartbeat" arrives within a second or two, the next six hours later, and one "Daily summary" after 01:00 UTC the next day.

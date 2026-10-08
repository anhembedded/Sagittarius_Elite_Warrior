# EPIC-036 — An alerting module: alerts reach the owner on more than one channel, and the owner can see what was sent

- **Status:** 🔵 Planned — scaffolded 2026-10-08; **not started** (the owner said: create it and leave it)
- **Repositories:** Elite. No Engine change is expected; a need for one gets its own confirmation (`ONBOARDING.md` §2).
- **Origin:** the owner's approval of the alerting design on 2026-10-08, relayed by the coordinator session: *"a bot that has trouble must reach me even when I am away from the machine; Discord first, Telegram exists, other channels later; many bots and many kinds of bot; leave room to control bots from Discord"* (paraphrased from the design page). It rewrites [`EPIC-035K`](../EPIC-035_spot_grid_unattended_safety/cancelled/EPIC-035K_alerts_reach_a_user_who_is_away.md), which asked for one Discord adapter behind a bots-owned port.
- **North star:** [`DESIGN_2026-10-08_alerting_module.md`](DESIGN_2026-10-08_alerting_module.md), the full English transcription of the owner-approved design (components, classes, four sequences, the many-bots table, the UI wireframes, N1–N8, the task split). The owner's page (Vietnamese, https://claude.ai/artifact/Q6J7i4FCLEhHXZiQtruAm1, `master-warrior` `1f890e0`) is a private artifact and a secondary reference only. Research behind it: [`RESEARCH_2026-10-08_alerting_lessons.md`](RESEARCH_2026-10-08_alerting_lessons.md). The points every task must carry are in §1b.
- **Decisions:** [`DECISION_2026-10-08_alerting_module.md`](DECISION_2026-10-08_alerting_module.md) — N1–N8 accepted.
- **Tracking:** [`TRACKING.md`](TRACKING.md).
- **Dependencies:** Builds on `BOT-018` (the `INotificationChannel` port, the Telegram channel and `NotificationEventHandler`, wired at `src/shell/composition_root.py:262-270`) and on `EPIC-034E` (the keyring-backed `ISecretStore`). The heartbeat (`EPIC-036E`) reads the health snapshot of [`EPIC-035W`](../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md); remote control (`EPIC-036F`) comes after [`EPIC-035X`](../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035X_every_bot_decision_is_in_an_audit_trail.md). Replaces [`EPIC-035K`](../EPIC-035_spot_grid_unattended_safety/cancelled/EPIC-035K_alerts_reach_a_user_who_is_away.md) as the home of Phase 3's alerts: [`EPIC-035L`](../EPIC-035_spot_grid_unattended_safety/completed/EPIC-035L_range_exit_and_start_outside_the_range.md) delivered the range-exit *fact* (`BotRangeChangedEvent`) and waits on `EPIC-036B` for the alert.

---

## 1. Decisions already made
All eight are the owner's, 2026-10-08, and are recorded in the [decision record](DECISION_2026-10-08_alerting_module.md).
1. **N1** — a new bounded context `src/modules/alerting`. It listens to `bots/contracts` and `trading/contracts` events; `bots` never imports it. The Telegram channel moves into `alerting/adapters`. The in-app `INotifier` (toasts, dialogs) stays as it is.
2. **N2** — a persistent outbox (SQLite under the data root's `state/`). An alert older than 24 h expires instead of being sent late.
3. **N3** — the Telegram token moves to the keyring (migrated once from config, then removed from config); the Discord webhook lives in the keyring only; `ISecretStore` is lifted to `core/contracts`.
4. **N4** — defaults: CRITICAL loud, WARNING silent, heartbeat every 6 h, no quiet-hours preset.
5. **N5** — per-bot alerts are On / Critical only / Off; Off needs a confirmation.
6. **N6** — remote control from Discord is a separate Phase-4 task after `EPIC-035X`; it reuses the UI's command handlers; commands are authorised by a user-ID allowlist, never through a webhook; the library is decided when the task starts and a new dependency needs owner approval.
7. **N7** — a dead man's switch: an adapter pings an external service (healthchecks.io or a URL the owner picks); off by default.
8. **N8** — CRITICAL goes to two channels when two or more are configured.

### 1b. What every task carries (the design's "lessons from real users")
- **A typed `Alert`:** kind, severity, subject, title, detail, at, dedup key. `AlertSubject` carries bot id, name, kind, venue and symbol. The `AlertKind` catalog includes `STOP_FAILED`.
- **`IAlertChannel.deliver(alert) -> DeliveryResult`** (`ok`, `retry_after`, `permanent`, `reason`) and it never raises.
- **Per channel:** its own queue; `retry_after` honoured and never retried earlier; a bounded number of retries, then `CHANNEL_FAILING`; CRITICAL fails over to another channel when `retry_after` exceeds 5 minutes.
- **Order:** a priority queue, CRITICAL first; INFO is dropped before CRITICAL ever is.
- **Loudness per route cell:** loud, silent (Discord `@silent`, Telegram `disable_notification`) or off.
- **Noise control:** dedup by key (a repeat updates one record with a counter); grouping by stable keys (kind + venue); inhibition (a venue-down alert suppresses the per-bot feed-stale alerts); a recovery message when the condition clears.
- **Secrets:** never in logs, errors, config or the UI; a "rotate webhook" action; Send test turns Telegram "chat not found" / a missing `/start` into plain guidance.
- **UI (QtWidgets, `IOptionsSection`, `configure_item_view`, `preview.py`):** Tools → Options → Alerts page, View → Alerts dock, a status-bar indicator, a per-bot Alerts item in the bot context menu with a muted-bell marker on the row.
- **Heartbeat** reads the same health snapshot as `EPIC-035W`.

## 2. Goals — measurable
| Metric | Today (measured 2026-10-08, `master-warrior` `1f890e0`) | When the epic is done |
| :--- | :-: | :-: |
| Bot safety events that reach an absent owner (HALT, ERROR, stop failed, stop-loss/take-profit, feed stale, stream down, key rejected, storage failure, range exit) | 0: the only source is `NotificationEventHandler`, which hears three system failures and no bot event | each has an `AlertKind` and one alert |
| Channels | 1 (Telegram), plus the in-app toast | Telegram and Discord; a third is one adapter file (proved by a fake channel) |
| Where the Telegram token lives | the config file | the keyring |
| An alert survives an app restart or a dead network | no: `send` is fire-and-forget, no retry | persisted in an outbox; sent on return, expired after 24 h |
| 20 bots losing the price feed at once | would be 20 messages, deduplicated only against the previous identical text (`notification_event_handler.py`) | one grouped message |
| The owner can see what was sent, to which channel, and what failed | nothing: a failure is a log line | the Alerts dock and the status-bar indicator |
| An app that died or a machine that went off | silent | an external service alerts the owner (the dead man's switch, off by default) |

## 3. Sub-tasks, ordered by risk
Each child is one PR, done in the order the dependencies allow. `EPIC-036F` is Phase 4 and is the only one whose start needs an owner decision (the library).

| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-036F](incomplete/EPIC-036F_remote_control_from_discord.md) | Remote control from Discord: `IRemoteCommandSource`, `RemoteCommandGate`, allowlist, command tiers, idempotency, audit (Phase 4) | Elite | 036A, 036C, 035X; library approved by the owner | 🔴 | Planned |
| [EPIC-036A](incomplete/EPIC-036A_alerting_core.md) | Alerting core: module skeleton, `Alert`, `IAlertChannel`, `AlertHub`, SQLite outbox, `DeliveryWorker`, `ISecretStore` lifted to core | Elite | None | 🟡 | Planned |
| [EPIC-036C](incomplete/EPIC-036C_discord_channel_and_telegram_migration.md) | Discord channel and Telegram migration: embeds, keyring, token migration, no-secret-in-logs, rate-limit tests | Elite | 036A | 🟡 | Planned |
| [EPIC-036E](incomplete/EPIC-036E_heartbeat_dead_mans_switch_and_summary.md) | Heartbeat, dead man's switch and daily summary | Elite | 036A, 036C, 035W | 🟡 | Planned |
| [EPIC-036B](incomplete/EPIC-036B_alert_sources.md) | Alert sources: `BotAlertSource`, `StreamAlertSource`, `SystemAlertSource` replacing `NotificationEventHandler` | Elite | 036A | 🟢 | Planned |
| [EPIC-036D](incomplete/EPIC-036D_alerts_ui.md) | UI: Options page, Alerts dock, status-bar indicator, per-bot mute, with previews | Elite | 036A, 036C | 🟢 | Planned |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1 — Core and sources | `036A` and `036B` merged: an event from a bot reaches a fake channel as one typed alert; a second fake channel needs no application change; the old handler is gone | Each child's red-before tests (named in the task); the `-Full` run green on each head; a reviewer's read. Not run |
| 2 — Real channels | `036C` merged: Discord and Telegram deliver, the token is in the keyring, no secret appears in a log or error, a 429 is never retried early | Per-child tests; a Discord webhook run and a Telegram run on the owner's own channels, recorded in the task. Not run |
| 3 — Visible and watched | `036D` and `036E` merged: the owner configures channels, sends a test, reads the history and mutes a bot from the app; a heartbeat and the dead man's switch work | Preview screenshots; a run in which the app is killed and the external service alerts. Not run |
| 4 — Remote control | `036F` merged: a command from an allowlisted Discord user stops a bot through the UI's own handler, once, and is audited | The owner's approval of the library recorded first; the task's tests; a run on the owner's Discord. Not run |

## 5. Out of scope
- The in-app `INotifier` (toasts and dialogs): unchanged; it is a notice inside the app, not an alert outside it.
- A channel beyond Discord and Telegram (email, SMS, a tray icon, a push service): each is one adapter on `IAlertChannel` and gets its own task when the owner wants it.
- Remote control through a webhook: never (N6). Remote control of Futures or of anything beyond stop, pause and status before `EPIC-036F` is designed.
- Exchange-side stop-loss: [`EPIC-026K`](../EPIC-026_road_to_real_money/README.md).
- The health strip and the truthful status bar: [`EPIC-035W`](../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md); the audit journal: [`EPIC-035X`](../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035X_every_bot_decision_is_in_an_audit_trail.md).
- Any code. This epic is documentation until a child task is started.

## Notes (newest first)
- **2026-10-08** — Epic scaffolded from the owner-approved design (N1–N8). `EPIC-035K` moved to `EPIC-035/cancelled/` as superseded. Documentation only; nothing started.

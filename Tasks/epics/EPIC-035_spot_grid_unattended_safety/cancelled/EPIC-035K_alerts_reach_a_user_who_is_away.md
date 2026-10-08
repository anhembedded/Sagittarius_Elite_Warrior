# EPIC-035K — Alerts reach a user who is away: a Discord notifier port and adapter

**Status:** ❌ Cancelled (2026-10-08; superseded by [EPIC-036](../../EPIC-036_alerting_module/README.md))
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M7 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 3 of [EPIC-035](../README.md).
**Risk:** 🟡 — a secret webhook URL and a new outbound network dependency
**Complexity:** L
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035A, EPIC-035B, EPIC-035C
**Superseded by:** [EPIC-036](../../EPIC-036_alerting_module/README.md) (A core, B sources, C channels, D UI, E heartbeat, F remote control)

---

> **Cancelled 2026-10-08 — superseded by [EPIC-036](../../EPIC-036_alerting_module/README.md).** The owner approved an alerting module (decisions N1–N8) instead of this task's port-in-`bots` plus one Discord adapter. Reason: an existing seam (`INotificationChannel`, `BOT-018`) is extended into `IAlertChannel` rather than a parallel port being added, and the scope grew past one adapter (routing, an outbox, history, a configuration page, a heartbeat and, later, remote control), which needs its own bounded context. Its criteria moved: alert kinds and sources to [036B](../../EPIC-036_alerting_module/incomplete/EPIC-036B_alert_sources.md), Discord and the webhook secret to [036C](../../EPIC-036_alerting_module/incomplete/EPIC-036C_discord_channel_and_telegram_migration.md), the Options page to [036D](../../EPIC-036_alerting_module/incomplete/EPIC-036D_alerts_ui.md), the heartbeat to [036E](../../EPIC-036_alerting_module/incomplete/EPIC-036E_heartbeat_dead_mans_switch_and_summary.md). Kept for history; do not execute.

## 1. Context and problem
Audit M7 and owner decision D3 (Discord). Today state changes are logged at INFO and the Bots tab refreshes; there is no OS, tray or push signal, so H1–H3 produce none at all. Cited: `src/modules/bots/application/services/bot_run_state.py:221-228`, `src/modules/bots/application/services/notifying_bot_store.py`. Verify.

This task is specified briefly: it is Phase 3 — Alerting and transparency. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] A port (`INotifier`-style, in the bots or a support contracts package) takes a typed alert (kind, bot id, reason, time); no Discord word appears in the application layer.
- [ ] A Discord adapter posts to a webhook. The webhook URL is stored in the keyring only (like the mainnet secret of `EPIC-034`) and is never in a log line, a config file, an exception message or a traceback; the adapter's own errors are sanitised.
- [ ] Alerts on HALT, ERROR, STOPPING stuck, price-feed stale, user-stream down, key rejected and range exit, plus a heartbeat on a named interval that says each bot's state; the heartbeat's absence is itself the alert.
- [ ] A Discord outage, a 429 or a revoked webhook never blocks or crashes a bot; sending is asynchronous, bounded and retried with backoff, and a failure to notify is shown in the app.
- [ ] Another channel is one new adapter on the same port (proven by a second, fake adapter in the tests).
- [ ] The Options page lets the owner enter, test and remove the webhook; the secret is never displayed back.

## 3. Design
Port and adapter (the project's own layering, `architecture-rule.md`); the keyring pattern of `EPIC-034E`; an outbox of undelivered alerts is considered and decided in the PR.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/ (the port)` | as the criteria require |
| `src/modules/bots/adapters/ (the Discord adapter)` | as the criteria require |
| `src/modules/trading/ui/settings/ (the Options entry)` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_halt_sends_one_alert`
- `test_the_webhook_url_never_appears_in_a_log_or_error` (red-flag test: scans captured logs and exception text)
- `test_a_failing_notifier_never_blocks_a_bot`
- `test_the_heartbeat_fires_on_the_interval`
- `test_a_second_adapter_needs_no_application_change`

Not run yet.

## Resume
Not started. Cancelled, superseded by `EPIC-036`.

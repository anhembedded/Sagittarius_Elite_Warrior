# ADR — Alerts leave the app through a new `alerting` module, a persistent outbox and channel adapters; remote control is a later, separate task

**Epic:** [EPIC-036](README.md)
**Date:** 2026-10-08
**Status:** Accepted (N1–N8)
**Decided by:** the owner, 2026-10-08, who approved the design page (https://claude.ai/artifact/Q6J7i4FCLEhHXZiQtruAm1) and its eight decision points; relayed by the coordinator session. The numbering N1–N8 is the design page's own.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

## 1. Context
✅ Established on `master-warrior` `1f890e0` (read 2026-10-08):
- `INotificationChannel.send(message: str) -> None` (`src/core/contracts/i_notification_channel.py`) carries a plain string: a channel cannot format, filter or tell a bot from a system failure.
- `TelegramNotificationChannel` (`src/infrastructure/notifications/telegram_notification_channel.py`) reads its token from the config reader, does not retry and only logs a failure.
- `NotificationEventHandler` (`src/shell/notification_event_handler.py`, wired at `src/shell/composition_root.py:262-270`) hears `UiActionFailedEvent`, `TaskFailed` and a failed bulk sync. It hears no bot event, and its debounce remembers only the previous message.
- `IOptionsSection` (`src/core/contracts/i_options_section.py`) is the contract for a page of Tools → Options. `ISecretStore` (`src/support/binance_gateway/contracts/i_secret_store.py`) is keyring-backed and used by `trading` and `binance_gateway` only.
- [`EPIC-035K`](../EPIC-035_spot_grid_unattended_safety/cancelled/EPIC-035K_alerts_reach_a_user_who_is_away.md) asked for a port in `bots`/`support` plus one Discord adapter. The owner's scope since is wider: a configuration page, per-alert and per-bot routing, a history, retries, a heartbeat and, later, commands from Discord. That has its own data, UI and lifecycle, so it is a bounded context.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| N1 | A new bounded context `src/modules/alerting`. It listens to `bots/contracts` and `trading/contracts` events; `bots` never imports `alerting`. The Telegram channel moves into `alerting/adapters`. The in-app `INotifier` (toasts, dialogs) stays | Accepted | 🟢 user decision, 2026-10-08 | A new kind of bot needs no change in `alerting`. `INotificationChannel` is not kept beside the new port: it is extended into `IAlertChannel` (BOT-018's seam is extended, not paralleled), and the toast channel's path is decided in `EPIC-036B` |
| N2 | A persistent outbox: SQLite under the data root's `state/`. An alert older than 24 h expires instead of being sent late | Accepted | 🟢 user decision, 2026-10-08 | Unsent alerts survive a restart and a dead network. An expired alert is marked so in the history, never sent late and never silently dropped |
| N3 | The Telegram token moves to the keyring (migrated once from config, then removed from config). The Discord webhook lives in the keyring only. `ISecretStore` is lifted to `core/contracts` | Accepted | 🟢 user decision, 2026-10-08 | No secret in config, log, error or UI. Importers of `i_secret_store` under `trading` and `binance_gateway` change their import; where the keyring adapter lives is settled in `EPIC-036A` |
| N4 | Defaults: CRITICAL loud, WARNING silent, heartbeat every 6 h, no quiet-hours preset | Accepted | 🟢 user decision, 2026-10-08 | A first run is useful without a page of settings; the owner opts in to quiet hours |
| N5 | Per-bot alerts are On / Critical only / Off. Off needs a confirmation | Accepted | 🟢 user decision, 2026-10-08 | A muted bot is marked on its row; CRITICAL of a bot set to Off needs the explicit confirmation |
| N6 | Remote control from Discord is a separate Phase-4 task. It comes after `EPIC-035X` (the audit trail) and reuses the UI's command handlers. Commands are authorised by a user-ID allowlist, never through a webhook. The library is decided when the task starts; a new dependency needs owner approval | Accepted | 🟢 user decision, 2026-10-08 | `EPIC-036F`. An empty allowlist accepts no command. The first remote command already has an audit record |
| N7 | A dead man's switch: an adapter pings an external service (healthchecks.io or a URL the owner picks). Off by default | Accepted | 🟢 user decision, 2026-10-08 | The only alert that survives the app dying. The ping URL is a secret (keyring) |
| N8 | CRITICAL goes to two channels when two or more are configured | Accepted | 🟢 user decision, 2026-10-08 | A phone push that never arrives (a known Android failure mode) is covered by the second channel; "delivered" means the platform accepted it, not that the owner read it |

## 3. Alternatives considered
- **A second port beside `INotificationChannel`, or a notifier in `bots` (EPIC-035K's plan).** Lost: two ports for one job, and `bots` would own what `trading` and the system also raise. Extending the existing seam (a `Protocol` today, `architecture-rule.md` §2.1) keeps one.
- **No module, only an adapter.** Lost: routing rules, history, retries, a heartbeat and a command gate are state with a lifecycle; they need an owner (Bounded Context).
- **A library for Discord/Telegram sending.** Lost: both are one POST; `urllib`, as Telegram does today, adds no dependency. Only the Phase-4 gateway needs one, and that is the owner's call.
- **Fire-and-forget with an in-memory queue.** Lost to N2: an alert raised while the network is down is the one that matters.
- **Webhook as the command path.** Rejected for security: a webhook carries no authentication.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Which Discord gateway library, or a hand-written client, for `EPIC-036F` (a new dependency) | `EPIC-036F` | 2026-10-08 |
| O2 | Where `KeyringSecretStore` lives once `ISecretStore` is in `core/contracts` (it is under `modules/trading/adapters/binance/mainnet/` today): `alerting` must not import `trading`'s adapter | `EPIC-036A` | 2026-10-08 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| N1 | [036A](incomplete/EPIC-036A_alerting_core.md), [036B](incomplete/EPIC-036B_alert_sources.md) | Not started | Not yet verified |
| N2 | [036A](incomplete/EPIC-036A_alerting_core.md) | Not started | Not yet verified |
| N3 | [036A](incomplete/EPIC-036A_alerting_core.md), [036C](incomplete/EPIC-036C_discord_channel_and_telegram_migration.md) | Not started | Not yet verified |
| N4 | [036A](incomplete/EPIC-036A_alerting_core.md), [036E](incomplete/EPIC-036E_heartbeat_dead_mans_switch_and_summary.md) | Not started | Not yet verified |
| N5 | [036A](incomplete/EPIC-036A_alerting_core.md), [036D](incomplete/EPIC-036D_alerts_ui.md) | Not started | Not yet verified |
| N6 | [036F](incomplete/EPIC-036F_remote_control_from_discord.md) | Not started | Not yet verified |
| N7 | [036E](incomplete/EPIC-036E_heartbeat_dead_mans_switch_and_summary.md) | Not started | Not yet verified |
| N8 | [036A](incomplete/EPIC-036A_alerting_core.md) | Not started | Not yet verified |

Status: Current

# `alerting` — 4. Solution strategy: the walking skeleton first

*Which few choices shape everything else, and in which order is the module built?*

**Built** (`EPIC-036G`). The thinnest slice that is useful to the owner and passes through every
seam the module has: an event from another module, a source, the hub, the persistent outbox, a lane,
a real channel, a secret from the host, and the host's own report. It is `EPIC-036G`
([task](../../../Tasks/epics/EPIC-036_alerting_module/completed/EPIC-036G_walking_skeleton_halt_to_discord.md));
everything else in `EPIC-036` hangs off it ([ADR 036 of 2026-10-15](../../../Tasks/epics/EPIC-036_alerting_module/DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md), D2).

## What it does

A bot that enters `HALTED` or `ERROR`, or whose stop gives up after its automatic retries (it stays
`STOPPING`, `src/modules/bots/application/kinds/grid/stop/grid_stop_retry.py` →
`GridStopRetry._exhausted`), produces exactly one CRITICAL alert (`BOT_HALTED`, `BOT_ERROR`,
`STOP_FAILED`), stored in the outbox before any send, and delivered to one Discord webhook. A 429 is
answered by waiting the time Discord names and never less. No log line, exception text or outbox row
holds the webhook URL or any part of it. It works on the headless VPS host, where the webhook comes
from a systemd credential file. The journey, drawn: [`06-runtime.md`](06-runtime.md).

## What is real and what stands in

| Part | In the skeleton | Notes |
| :--- | :--- | :--- |
| `AlertHub`, `AlertRouter`, `DeliveryAdmission`, `SqliteOutbox`, `ChannelDelivery`, `ThreadedDeliveryHost`, `WakeSignal` | **Real, built** (`EPIC-036A`) | Unchanged. Dedup, grouping, inhibition and quiet hours run but are not configured |
| `BotAlertSource` | **Real, new, narrow** | Three kinds only; the full (state, reason) → kind table with its completeness test is `EPIC-036B` |
| A bots event for "the stop gave up" | **Real, new** in `bots/contracts/events/` | Today the give-up is only text in the bot's reason and an ERROR log; the source must not parse text (ADR of 2026-10-15, D4) |
| `DiscordWebhookChannel` | **Real, new, plain** | One message with the subject, title and detail; Discord's silent flag for a silent cell; no mention parsed; 429 → `retry_later` with Discord's wait, any other 4xx → `refused`, timeout or 5xx → `failed`. Embeds, colours and pacing are `EPIC-036C` |
| `IWebhookTransport` with `UrllibWebhookTransport` | **Real, new** | `urllib`, no new dependency (N1, design 036 §2) |
| `ISecretStore` for the webhook | **Real**: the systemd-credential store on the VPS, the keyring on a desktop | Lifted out of `trading` into `src/support/secrets/` (D3) |
| `IAlertingStatus` and the `operations` adapter | **Real, new** | `True` only when the Discord channel is configured (its webhook stored) and not disabled, so `run` stops warning only then |
| `alert test` | **Real, new** | The headless Send test; calls the channel once with an INFO test alert, prints the sanitised outcome |
| `JsonAlertSettings` | **Real, partly** (`BOT-191`) | Each bot's mode survives a restart in `<data root>/state/alert_settings.json`; routes, disabled channels and quiet hours are not editable yet and stay N4's defaults (`EPIC-036D`). `InMemoryAlertSettings` remains the tests' stand-in |
| The Options page's per-bot choice (All messages, Critical only, None) | **Real, new** (`BOT-191`) | Applies to the next alert without a restart; a bot set to Critical only sends no fill message and still sends its halts |
| The Options page's Discord webhook, Save, Remove and Send test | **Real, new** (`EPIC-036D1`) | The one place a desktop owner configures the channel; a first save or a removal takes effect after a restart ([`06-runtime.md`](06-runtime.md)) |
| Telegram, stream and system sources, the rest of the UI, the heartbeat, the dead man's switch, remote control | **Absent** | `EPIC-036C`, `036B`, `036D`, `036E`, `036F` |

## How it is proven

1. **End to end with a fake Discord**:
   `tests/integration/modules/alerting/test_a_halted_bot_reaches_discord.py` boots `create_app()`
   with the real `bots` and `alerting` graphs and the real outbox, rebinding only the secret store,
   the alert clock, the webhook transport and the market stream on the container. A bot written
   `HALTED` through the bots' store is posted once, Discord's 429 holds the retry until the clock
   reaches 2 s, the row ends `SENT`, and the log holds no part of the webhook; `ERROR` and a stop that
   gave up each reach Discord once; without a webhook nothing is posted and the host still warns.
   Removing the `bus.on(BotChangedEvent, ...)` line from `boot()` turns it red. The red-flag unit test
   (`tests/unit/modules/alerting/adapters/test_discord_webhook_channel.py`) runs every Discord answer
   through the real hub, worker pass and outbox and scans the log, the reasons and the SQLite files.
2. **The owner's manual Send test on the VPS**: the credential file provisioned, the unit
   regenerated and restarted, `alert test` run with the unit's credential
   (`Docs/OPERATIONS/headless_runbook.md` §5), and a message arriving in the owner's Discord channel;
   then `run` starting without the "no alert channel" warning. Not yet run: it is the owner's, and
   the task records it.

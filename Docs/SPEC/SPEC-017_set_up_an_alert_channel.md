Status: Current

# SPEC-017 — Set up an alert channel, so a halted bot reaches me

- **Status:** 🟡 partly built — the Discord webhook and the Telegram bot can be saved, replaced, removed and tested from Tools → Options → Alerts (`EPIC-036D1`, `EPIC-036D4`). Not built: the routing matrix (which alerts go to which channel and how loudly), the quiet-hours schedule, a channels table view.
- **Actor:** trader, operator (the owner, at the desktop)
- **Origin:** `EPIC-036` decisions N1–N8; the owner's 2026-10-16 request for the Options page.
- **Surfaces:** Tools → Options → Alerts; on a server with no window, `alert test` and the systemd credentials of `Docs/OPERATIONS/headless_runbook.md`.

## 1. Trigger
*"I want the app to tell me on my phone when a bot halts, even when I am away."*

## 2. Preconditions
- The operating system's keyring can store a secret (or the host provisions the credentials another way).
- For Discord, a channel webhook URL; for Telegram, a bot token from @BotFather and the id of the chat the bot may write to (the owner has sent the bot a message first).

## 3. Main flow
1. The owner opens Tools → Options → Alerts.
2. The page shows, for each channel, a line saying whether it is on and a line saying what is saved (the last four characters of the secret, and the Telegram chat id).
3. The owner pastes a Discord webhook URL or enters a Telegram bot token and chat id, and presses Save.
4. The app checks each value against the shape the platform issues, stores it in the keyring, reads it back, clears the fields and says what to do next: a first save takes effect after a restart (the channel's lane starts at boot), a replaced one at the next send.
5. The owner presses Send test: one loud test message goes to every channel that is set up, and the page names the channels it reached or says why one refused.
6. To replace a secret the owner saves again; to stop a channel the owner presses Remove and answers a question whose safe choice is Keep.

## 4. What must be true afterwards
The secret is in the keyring and nowhere else: not in a file, a log, an exception text or on the screen except its last four characters. The test message reached the phone.

## 5. When it goes wrong
| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| A value is empty or not of the platform's shape | A sentence naming which value and where to find it; nothing is saved and an earlier one is kept | validation is an outcome, not an exception |
| The keyring cannot store a secret | A sentence saying to unlock or enable it; nothing is saved | the store's refusal is an outcome |
| Another store answers first (a systemd credential) | "Saved, but this machine reads the credentials from … first" | the read-back catches it |
| A test is refused (404, a blocked bot) | The channel's own plain reason and what to check | the channel never raises |
| An unexpected exception | A message box naming only the exception's type | a secret can ride an exception text |

## 6. What this use case does NOT promise
- That a message reached a person: the platform accepted it.
- That a first save sends at once: the lane needs a restart.
- Which alerts go to which channel, and quiet hours: the routing matrix and the schedule are not built; the app's defaults apply.

## 7. Ports and modules it exercises
`alerting`: `DiscordWebhookSetup`, `TelegramCredentialsSetup`, `SendTestToConfiguredChannels`, `IChannelCatalogBuilder`; `ISecretStore`.

## 8. Proven by
| Evidence | Where | Tier |
| :--- | :--- | :--- |
| Telegram save, replace, remove, state; no token anywhere | `tests/unit/modules/alerting/application/test_telegram_credentials_setup.py` | unit |
| The Telegram group on the page, the Send test for every channel | `tests/unit/modules/alerting/ui/options/test_alerts_page_telegram.py` | unit |
| The Discord webhook | `tests/unit/modules/alerting/ui/options/test_alerts_page_webhook.py` | unit |
| The page, light and dark, three sizes | `tests/integration/modules/alerting/test_alerts_options_page_frames.py` | integration |
| **The user runs it:** save a real Telegram bot, restart, press Send test and read the message on the phone | — | manual |

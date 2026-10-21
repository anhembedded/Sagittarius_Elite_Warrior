Status: Current

# SPEC-017 — Set up an alert channel, so a halted bot reaches me

- **Status:** 🟡 built, the owner has not seen it in the real window — the Discord webhook and the Telegram bot can be saved, replaced, removed and tested from Tools → Options → Alerts (`EPIC-036D1`, `EPIC-036D4`), the quiet hours, the routing matrix, the channel switches and the heartbeat interval are set there too (`EPIC-036D6`–`EPIC-036D9`). Not built: a channels table with Add, Edit and Rotate (the groups above do it), a last-send column, the dead man's switch URL field.
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
7. Under Quiet hours the owner checks "Hold Warning and Info alerts during these hours", picks a From and a To time and presses Save quiet hours; the line above says what is held and in which zone. The times are read in the display time zone as it is when the owner saves, and kept with that zone's name. During the period the app holds Warning and Info alerts and sends one summary when it ends; Critical alerts are never held. Clearing the box and pressing Save turns it off.
8. Under Who hears what the owner sees one row per kind of alert (bot events, app and exchange problems, notices, routine messages) and one column per channel that is running, with a choice in each cell: Default, Loud, Silent or Off. A choice acts at once and the page says so. Default is Loud for a Critical alert and Silent for the rest; choosing Default again puts the cell back, so a later change of the defaults still reaches it. A Critical alert still reaches two channels when two are set up, and at least one of them rings, whatever the matrix says.
9. Under Channels the owner sees a check box for each channel that is running. Clearing one switches that channel off at once: its webhook or bot stays saved and nothing is sent there until the box is ticked again. If every channel is off the page says no alert is sent anywhere, a Critical one included.
10. Under Heartbeat the owner chooses how often the app sends its "bots are running" message: 1, 2, 3, 6, 12 or 24 hours, the default being 6. A choice acts at once and the next heartbeat follows the new interval without a restart.

## 4. What must be true afterwards
The secret is in the keyring and nowhere else: not in a file, a log, an exception text or on the screen except its last four characters. The test message reached the phone.

## 5. When it goes wrong
| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| A value is empty or not of the platform's shape | A sentence naming which value and where to find it; nothing is saved and an earlier one is kept | validation is an outcome, not an exception |
| The keyring cannot store a secret | A sentence saying to unlock or enable it; nothing is saved | the store's refusal is an outcome |
| Another store answers first (a systemd credential) | "Saved, but this machine reads the credentials from … first" | the read-back catches it |
| A test is refused (404, a blocked bot) | The channel's own plain reason and what to check | the channel never raises |
| A choice is made for a channel that is not running in this session | A sentence saying the choice would reach nothing and to restart after setting the channel up; nothing is kept | a route for a channel that never sends would only look saved |
| The quiet hours' start and end are the same time | A sentence saying that is no quiet period; nothing is kept | an empty period would read "saved" over something that never starts |
| The settings file cannot be written | A sentence saying the quiet hours are as they were | the store's refusal is an outcome |
| An unexpected exception | A message box naming only the exception's type | a secret can ride an exception text |

## 6. What this use case does NOT promise
- That a message reached a person: the platform accepted it.
- That a first save sends at once: the lane needs a restart.
- That Off or Silent in every cell silences a Critical alert: the router keeps a second channel for it (N8) and one loud delivery. The heartbeat's interval is not editable.

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

Status: Current

# SPEC-016 — See what the app told me, and whether it is getting through

- **Status:** 🟡 partly built — the Alerts mode shows the stored alerts and each channel's delivery, and says when a channel is failing (`EPIC-036D2`). Not built yet: the channels table with Send test and Rotate, the routing matrix, the quiet-hours schedule, a status-bar indicator, a per-bot mute in the bots list and "Retry failed" (the rest of `EPIC-036D`).
- **Actor:** trader, operator (the owner, at the desktop, after being away)
- **Origin:** `EPIC-036` decision N1–N8 ("the owner can see what was sent, to which channel, and what failed"); slice `EPIC-036D2`.
- **Surfaces:** the Alerts mode (the bell on the mode bar), View → Alerts.

## 1. Trigger

*"I was away. Did the app tell me anything, did it reach my phone, and is a channel broken?"*

## 2. Preconditions

- The app is running with the alerting module booted (it is, in every normal run).
- For a delivery to be listed, the run has raised at least one alert; the list itself needs nothing else.

## 3. Main flow

1. The owner opens the Alerts mode.
2. The app reads the stored alerts off the UI thread and shows them newest first: the time it was first raised, severity in words (Info, Warning, Critical), what it was about, the alert's title (with how many times it happened when more than once) and, per channel, where it stands: delivered, waiting, retrying ×n, failed ×n, expired or dropped.
3. Above the table one line names every configured channel as working or failing, with how many deliveries are waiting.
4. When a channel's newest real delivery did not get through (failed, expired, or retrying after a failed try; a wait the platform or the pacing asked for is not a failure), a notice says which channel and points to Tools → Options → Alerts.
5. The owner narrows the list with the severity filter (All, Warning and above, Critical only); no second read is made.
6. The list is read again every fifteen seconds and when the owner presses Refresh.

## 4. What must be true afterwards

The owner can say, from the screen alone, which alerts were raised, which channel each reached and which channel is failing. Nothing was sent or changed by looking.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| No alert has been raised yet | An empty table with the sentence saying alerts appear when one is raised | the empty state is a named text |
| No channel is configured | The channel line says nothing leaves the app and where to add a Discord webhook | a missing webhook is a state, not an error |
| An alert reached no channel (muted, or no route) | "not sent (muted, or no channel for it)" in its Delivery cell | the outbox stores such an alert on purpose |
| The history cannot be read | The last list stays, with a sentence naming the exception's type and pointing to the log | a failed read is reported by type only; the list is never cleared by it |

## 6. What this use case does NOT promise

- That a delivery marked "delivered" was read by a person: it says the channel accepted it.
- That the list is live to the second: it is read every fifteen seconds.
- Colour: severity and state are words today; a colour comes with the shared meaning table of `EPIC-043`.
- Anything beyond the newest 500 alerts.

## 7. Ports and modules it exercises

`alerting`: `IAlertHistory`, `IOutbox`, `IAlertChannelCatalog`; the shell's mode bar and View menu.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| The history read model, channel health | `tests/unit/modules/alerting/application/test_outbox_alert_history.py` | unit |
| The screen: words, filter, notice, failed read, stale answer | `tests/unit/modules/alerting/ui/history/test_alerts_screen.py` | unit |
| The frames, light and dark, three window sizes | `tests/integration/modules/alerting/test_alerts_frames.py` | integration |
| The module contributes the screen; the surface is the shell's | `tests/unit/modules/alerting/test_alerting_module.py` | unit |
| The workbench rules hold with the mode present | `tests/integration/presentation/ui/test_workbench_conformance.py` | integration |
| **The user runs it:** store a Discord webhook the network cannot reach, let any alert be raised (a bot halting), open Alerts and see the Discord line say failing, the notice name Discord and the alert's Delivery cell say retrying or failed | — | manual |

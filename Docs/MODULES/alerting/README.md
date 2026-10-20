Status: Current

# `alerting` — the module that carries an alert to the owner when the owner is away

**Reader:** someone building the next alerting task (`EPIC-036`), adding a channel or an alert
source, or deciding whether the headless host can be left alone with real money.
**Question it answers:** *when something the owner must know happens, how does it reach them, once,
even if a channel is down, the platform asks us to wait, or the app restarts?*

Each fact in this folder is marked **Built** (on `master-warrior`, delivered by `EPIC-036A` and the
walking skeleton `EPIC-036G` and the Options page slice `EPIC-036D1`, cited by path and symbol) or **Planned** (designed here, not written; the task
that builds it is named). Paths are from the repository root; `alerting/` means
`src/modules/alerting/`. The layout is the template's, [`../README.md`](../README.md).

## Which file to read

| You want to know | Read |
| :--- | :--- |
| What crosses the module's edge, in and out | [`03-context.md`](03-context.md) |
| Why the walking skeleton came first, what in it is real and what stands in, and how it is proven | [`04-solution-strategy.md`](04-solution-strategy.md) |
| Which classes carry an alert, and the domain types and contracts | [`05-building-blocks.md`](05-building-blocks.md) |
| One alert from `publish` to Discord, step by step | [`06-runtime.md`](06-runtime.md) |
| Which thread does what; the outbox file; the headless host and its credential | [`07-deployment.md`](07-deployment.md) |
| What is stored, in what shape, and what is in memory on purpose | [`08-concepts.md`](08-concepts.md) |
| The decision records behind the module | [`09-decisions.md`](09-decisions.md) |
| The constants that decide when an alert is merged, retried, failed over, expired or purged | [`10-quality.md`](10-quality.md) |
| A delivery's states, and how the bot source reads the bots lifecycle | [`state-machines.md`](state-machines.md) |

## Built and Planned, at a glance

| Part | State | Task |
| :--- | :--- | :--- |
| The hub, the outbox, the lanes, dedup, grouping, inhibition, quiet hours | **Built** | `EPIC-036A` |
| The bot source, the Discord channel, `alert test`, the host's warning | **Built** | `EPIC-036G` (waits for the owner's VPS run) |
| Early warnings: a Futures bot near liquidation, a user-data stream down past a grace | **Built** | `EPIC-036B1` |
| A bot's reason chooses its alert: rate limit, rejected key, storage pause, a price feed that stays quiet; the reason table and its completeness test | **Built** | `EPIC-036B2` |
| The app's own failures (`APP_FAILURE`: a task that died, a failed sync, a UI slot that raised) replacing the old notification handler and its direct Telegram wiring | **Built** | `EPIC-036B` |
| Telegram moved in, embeds, pacing, secret rotation | Planned | `EPIC-036C` |
| Each channel paced under its platform's rate limit; the worker's lane sleeps no longer than the channel's wait | **Built** | `EPIC-036C2` |
| Tools → Options → Alerts: the Discord webhook, Save, Remove, Send test | **Built** | `EPIC-036D1` (waits for the owner's look at the real window) |
| The rest of the Options page (channels table, routing matrix, schedule), the Alerts dock, persisted settings | Planned | `EPIC-036D` |
| The dead man's switch: a ping to an external monitor while the alert worker is alive | **Built** | `EPIC-036E1` (waits for the owner's kill test on the VPS) |
| The heartbeat message and the daily summary | Planned | `EPIC-036E` |
| Remote control from Discord | Planned | `EPIC-036F` |

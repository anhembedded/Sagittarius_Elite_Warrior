# BOT-191 — The owner mutes the fill messages of one bot

**Status:** ✅ Done (2026-10-19)
**Priority:** P3
**Board:** Nothing set a bot's alert mode and alert settings were in memory; the Options page's Alerts section now lists every bot with All messages / Critical only / None, kept in `<data root>/state/alert_settings.json` and applied to the next alert. A missing, older, newer or damaged file is every default (all bots tell everything); a bot set to Critical only sends no fill message and still sends its halts.
**Source:** `BOT-189` review round 1 (PR #572), recorded as a limit; recommended by the author.
**Risk:** 🟢 — settings only; the router already honours the mode.
**Complexity:** M — a store for `AlertSettings` that survives a restart (the Options page of `EPIC-036D`) and a control per bot.
**Epic (optional):** [EPIC-036](../epics/EPIC-036_alerting_module/README.md)
**Depends on:** `BOT-189`; `EPIC-036D` (the persistent settings store).

---

## 1. Context and problem
`InMemoryAlertSettings` holds N4's defaults and no persistence (`adapters/memory_alert_settings.py`); `AlertRouter._bot_allows` already drops a bot's INFO/WARNING under `CRITICAL_ONLY` and everything under `OFF`.

## 2. Acceptance criteria
- [x] The owner sets a bot to On, Critical only or Off, and it survives a restart.
- [x] A bot set to Critical only sends no fill message and still sends its halts.

## 3. Design
One file, one port, one page section.
- **Store.** `JsonAlertSettings` (adapter) serves both `IAlertSettingsSource` (the hub reads it for every alert, so an edit applies to the next one) and the new `IBotAlertModes` (`modes`, `set_mode`; the page edits through it). The file is `<data root>/state/alert_settings.json`, `{"schema": "sew.alert-settings/1", "bot_modes": {"<bot id>": "<mode>"}}`; only the per-bot modes are persisted, the routes, disabled channels and quiet hours stay N4's defaults until `EPIC-036D` gives them a control. A mode `on` is not written.
- **What a missing or older file does.** A missing file is every default (all bots `on`) and nothing creates it until the owner sets a mode. A file this build cannot read (not JSON, a schema other than `/1`) is every default, told once in the log (`[alert-settings]`), left untouched, and moved aside to `alert_settings.json.unreadable` on the owner's next save. One entry with a mode this build does not know is skipped and the rest kept. The default is the loud side on purpose: an alert system must fail toward more messages, never fewer.
- **Page.** A "Bots" group in Tools → Options → Alerts: one row per bot (the bots' status report, the same read the alert sources use), a combo of the three modes; a change runs through the page's existing off-thread action machinery and republishes the rows from what is really kept, so a failed write shows the old value and says so.
- **Read-only copy.** A second instance keeps a change in memory and writes nothing.

## 3a. Reuse
`BotAlertMode`, `AlertSettings.bot_modes`, `IAlertSettingsSource`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `alerting/contracts/i_bot_alert_modes.py` | the port the page edits through |
| `alerting/adapters/json_alert_settings.py` | the file store, tolerant of a missing, older, newer or damaged file |
| `alerting/composition/alerting_bindings.py` | binds it for both ports; `alert_settings_path` |
| `alerting/ui/options/*` | the Bots group: words, view model rows, view, presenter action, preview |
| `Docs/MODULES/alerting/04, 05, 08` | the store, the file and its tolerance |

## Implementation notes (written when done)
Tests: the adapter over real files (absent, round trip, back to On, four foreign shapes, not JSON, an unknown mode, read-only, a failed write), the page over the real file (list, choose, survive a reopen, a refused write, no bots, an unknown value), and on the fake exchange with the real hub and Discord channel a bot set to Critical only sends no fill and still sends its stop loss, and the choice is there after a restart. The mutation that stops the presenter calling `set_mode` turns three tests red. `BUG-233` was filed in the same documents commit for the flaky burst-of-starts test seen on PR #585.

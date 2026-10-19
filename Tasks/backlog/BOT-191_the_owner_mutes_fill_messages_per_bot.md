# BOT-191 — The owner mutes the fill messages of one bot

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** `BotAlertMode` exists but nothing sets it (alert settings are in memory), so `BOT-189`'s fill messages go out for every bot and only Discord's own channel mute silences them; a per-bot mode in the Options page, persisted, would let one noisy grid be set to critical-only.
**Source:** `BOT-189` review round 1 (PR #572), recorded as a limit; recommended by the author.
**Risk:** 🟢 — settings only; the router already honours the mode.
**Complexity:** M — a store for `AlertSettings` that survives a restart (the Options page of `EPIC-036D`) and a control per bot.
**Epic (optional):** [EPIC-036](../epics/EPIC-036_alerting_module/README.md)
**Depends on:** `BOT-189`; `EPIC-036D` (the persistent settings store).

---

## 1. Context and problem
`InMemoryAlertSettings` holds N4's defaults and no persistence (`adapters/memory_alert_settings.py`); `AlertRouter._bot_allows` already drops a bot's INFO/WARNING under `CRITICAL_ONLY` and everything under `OFF`.

## 2. Acceptance criteria
- [ ] The owner sets a bot to On, Critical only or Off, and it survives a restart.
- [ ] A bot set to Critical only sends no fill message and still sends its halts.

## 3. Design
Not written.

## 3a. Reuse
`BotAlertMode`, `AlertSettings.bot_modes`, `IAlertSettingsSource`.

## 4. Changes, per file
Written when the task starts.

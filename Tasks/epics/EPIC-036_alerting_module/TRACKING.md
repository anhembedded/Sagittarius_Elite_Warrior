# EPIC-036 — Tracking

- **Epic:** [EPIC-036](README.md)
- **Status:** 🟡 In progress (5/10) — `036A` done 2026-10-13; `036G` and `036D1` done 2026-10-16; `036E1` and `036B1` done 2026-10-20
- **Target Completion:** not set; each task is one pull request
- **Renders:** GitHub Markdown, VS Code Mermaid preview, or mermaid.live.

---

## 1. Schedule (Gantt)

```mermaid
gantt
    title EPIC-036 - Alerting module
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m

    section Spec
    Design approved, epic scaffolded      :done, s1, 2026-10-08, 1d

    section Phase 0 - Walking skeleton
    036A Alerting core                    :done, a, after s1, 5d
    036G Halt to one Discord webhook      :done, g, after a, 4d

    section Phase 1 - Sources
    036B1 Early warnings                  :done, b1, after g, 1d
    036B Alert sources, the rest          :b, after g, 3d

    section Phase 2 - Real channels
    036C Discord and Telegram migration   :c, after g, 5d

    section Phase 3 - Visible and watched
    036D1 Options page: Discord webhook  :done, d1, after g, 1d
    036D UI, the rest                     :d, after c, 5d
    036E1 Dead man's switch               :done, e1, after g, 1d
    036E Heartbeat and daily summary      :e, after c, 3d

    section Phase 4 - Remote control
    036F Remote control from Discord      :f, after e, 8d
```

---

## 2. Sub-tasks & PR Matrix

| Id | Sub-task | Branch / PR | Risk | Status | Target / Merged |
| :--- | :--- | :--- | :-: | :--- | :--- |
| EPIC-036A | [Alerting core](completed/EPIC-036A_alerting_core.md) | `claude/epic-036a-alerting-core` | 🟡 | ✅ Done (2026-10-13), awaiting merge | — |
| EPIC-036G | [Walking skeleton: halt to one Discord webhook](completed/EPIC-036G_walking_skeleton_halt_to_discord.md) | — | 🟡 | ✅ Done (2026-10-16), awaiting merge of this record | — |
| EPIC-036B1 | [Early warnings: liquidation, user-data stream](completed/EPIC-036B1_early_warnings_liquidation_and_user_stream.md) | `claude/epic-036b1-early-warnings` | 🟢 | ✅ Done (2026-10-20), awaiting merge | — |
| EPIC-036B | [Alert sources, the rest](incomplete/EPIC-036B_alert_sources.md) | — | 🟢 | 🔵 Planned | — |
| EPIC-036C | [Discord channel and Telegram migration](incomplete/EPIC-036C_discord_channel_and_telegram_migration.md) | — | 🟡 | 🔵 Planned | — |
| EPIC-036D1 | [Options page: the Discord webhook, Send test](completed/EPIC-036D1_options_alerts_page_discord_webhook.md) | `claude/alerts-options-page-036d1` | 🟡 | ✅ Done (2026-10-16), awaiting merge of this record | — |
| EPIC-036D | [UI, the rest](incomplete/EPIC-036D_alerts_ui.md) | — | 🟢 | 🔵 Planned | — |
| EPIC-036E1 | [Dead man's switch](completed/EPIC-036E1_dead_mans_switch.md) | `claude/epic-036e1-dead-mans-switch` | 🟡 | ✅ Done (2026-10-20), awaiting merge | — |
| EPIC-036E | [Heartbeat and daily summary](incomplete/EPIC-036E_heartbeat_dead_mans_switch_and_summary.md) | — | 🟡 | 🔵 Planned; waits for 035W | — |
| EPIC-036F | [Remote control from Discord](incomplete/EPIC-036F_remote_control_from_discord.md) | — | 🔴 | 🔵 Planned; waits for 035X and the owner's library approval | — |

---

## 3. Milestone & Status Log

| Date | Item | Event & Outcome |
| :--- | :--- | :--- |
| 2026-10-08 | Spec | Design approved by the owner (N1–N8); epic scaffolded with six children; `EPIC-035K` superseded. Documentation only. |
| 2026-10-16 | 036G, 036D1 | Closed with the owner's recorded runs: `alert test` from the VPS and Send test from the Options page both reached Discord. No real halt on the VPS yet. |
| 2026-10-16 | 036D1 | Slice of `036D` the owner asked for: Tools → Options → Alerts with the Discord webhook, Save, Remove and Send test. Built; waits for the owner's look at the real window. |
| 2026-10-20 | 036E1 | The dead man's switch split off `036E` and built without `035W` ([decision](DECISION_2026-10-20_dead_mans_switch.md)); tests green; the owner's kill test on the VPS not run. |
| 2026-10-15 | Design | The design moves to `Docs/MODULES/alerting/` (`EPIC-041`'s standard); walking skeleton `036G` added first, `036B`/`036C`/`036E` re-sequenced behind it ([decision](DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md)). Documentation only. |
| 2026-10-16 | 036G | Walking skeleton built and verified (unit, sanity, integration; a real `alert test` reached Discord and got its 404 for a webhook that does not exist); the owner's run on the VPS is the open criterion. |

---

## 4. Blockers & Dependencies

| Blocker / Dependency | Impacted Tasks | Resolution / Owner | Status |
| :--- | :--- | :--- | :-: |
| The health snapshot of [`EPIC-035W`](../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md) (the owner asked that it not be started yet) | 036E | Land 035W first, or 036E ships without the heartbeat body and adds it after | 🟡 Open |
| The owner's answers on O1 (the webhook as a systemd credential, D3) and O2 (the host's warning, D5) of the [2026-10-15 decision](DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md) | 036G | The owner: both accepted 2026-10-16 | ✅ Closed |
| The audit journal of [`EPIC-035X`](../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035X_every_bot_decision_is_in_an_audit_trail.md) | 036F | Land 035X first | 🟡 Open |
| A Discord gateway library is a new dependency (`requirements.txt`, `ONBOARDING.md` §7) | 036F | The owner approves the library when 036F starts | 🟡 Open |

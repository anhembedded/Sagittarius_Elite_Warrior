# EPIC-029 — Tracking

- **Epic:** [EPIC-029](README.md)
- **Status:** 🟡 In progress (PR1–PR6 merged; PR7: 029H's tests in review; then the user's Spot Testnet soak)
- **Target completion:** the fast track (029A–029H) is estimated in working days below. The dates are
  a plan, not a commitment.
- **Renders:** GitHub Markdown, VS Code Mermaid preview, or mermaid.live.

---

## 1. Schedule (Gantt)

```mermaid
gantt
    title EPIC-029 - Bots tab and the Grid fast track
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m
    todayMarker stroke-width:2px,stroke:#d33,opacity:0.6

    section Plan
    PRO-006 accepted                         :done,    s1, 2026-10-03, 1d
    ADR review and user answers D6 O1-O5     :done,    s2, after s1, 1d

    section F0 Seams
    029A Trading seams for bots              :done,    a, after s2, 4d
    029B bots module, entity, store          :done,    b, after s2, 1d

    section F1 Planner
    029C Grid planner and indicators         :done,    c, after b, 1d

    section F2 Live bot and backtest
    029G Bot chart and shared live chart     :done,    g, after c, 3d
    029E Live Grid executor                  :done,    e, after a c, 5d
    029F Bots tab                            :done,    f, after g, 5d
    029D Grid backtest (parallel)            :         d, after g, 4d

    section F3 Testnet
    029H Spot Testnet soak and report        :crit,    h, after e f d, 3d
    Fast track done                          :milestone, m1, after h, 0d

    section After the fast track
    029I Desks manual only                   :         i, after m1, 3d
    029J Many bots                           :         j, after m1, 3d
    029K Grid on Futures                     :         k, after j, 5d
    029L Signal and DCA kinds                :         l, after i j, 5d
```

---

## 2. Sub-tasks & PR Matrix

| Id | Sub-task | Branch / PR | Risk | Status | Target / Merged |
| :--- | :--- | :--- | :-: | :--- | :--- |
| EPIC-029A | [Trading seams for bots](completed/EPIC-029A_trading_seams_for_bots.md) | — | 🔴 | ✅ Done (2026-10-03) | PR2 |
| EPIC-029B | [bots module, entity, store](completed/EPIC-029B_bots_module_entity_and_store.md) | PR1 (`claude/wizardly-cerf-fc5b5x`) | 🟡 | ✅ Done, in review | — |
| EPIC-029C | [Grid planner](completed/EPIC-029C_grid_planner.md) | PR1 (`claude/wizardly-cerf-fc5b5x`) | 🟢 | ✅ Done, in review | — |
| EPIC-029D | [Grid backtest](completed/EPIC-029D_grid_backtest.md) | — | 🟡 | ✅ Done (2026-10-04) | PR6 |
| EPIC-029E | [Live Grid executor](completed/EPIC-029E_live_grid_executor.md) | — | 🔴 | ✅ Done (2026-10-04) | PR4 |
| EPIC-029F | [Bots tab](completed/EPIC-029F_bots_tab.md) | — | 🟡 | ✅ Done (2026-10-04) | PR5 |
| EPIC-029G | [Bot chart](completed/EPIC-029G_bot_chart.md) | — | 🟡 | ✅ Done (2026-10-04) | PR3 |
| EPIC-029H | [Spot Testnet soak](incomplete/EPIC-029H_spot_testnet_grid_soak.md) | — | 🟡 | 🟡 In progress | PR7 (tests); soak by the user |
| EPIC-029I | [Desks manual only](incomplete/EPIC-029I_desks_manual_only.md) | — | 🟡 | 🔵 Planned | — |
| EPIC-029J | [Many bots](incomplete/EPIC-029J_many_bots.md) | — | 🟡 | 🔵 Planned | — |
| EPIC-029K | [Grid on Futures](incomplete/EPIC-029K_grid_on_futures.md) | — | 🔴 | 🔵 Planned | — |
| EPIC-029L | [Signal and DCA kinds](incomplete/EPIC-029L_signal_and_dca_kinds.md) | — | 🟡 | 🔵 Planned | — |

---

## 3. Milestone & Status Log

| Date | Item | Event & Outcome |
| :--- | :--- | :--- |
| 2026-10-03 | Plan | `PRO-006` accepted by the user. Epic, ADR (D1–D20, O1–O4) and 12 sub-tasks written, for an independent review (PR #317). |
| 2026-10-03 | Review r1 | NEEDS_REVISION: 5 blocking, 11 should-fix. All addressed; the ADR is now D1–D21 and O1–O5. Re-review requested. |
| 2026-10-03 | Review r2 | NEEDS_REVISION, narrower: 3 blocking (untagged Emergency Stop sells, unsliced exits, orders without a budget), 5 should-fix. All addressed. Re-review requested. |
| 2026-10-03 | Design merged | PR #317 merged by the user. The user answered D6 (own budget), O5 (keep the cap, configurable), O1–O4; the ADR is Accepted. Rule: two small tasks per PR. |
| 2026-10-03 | PR1 | `029B` (the `bots` module) and `029C` (the Grid planner) built; the report's example reproduced as known answers; a mutation run left 4 equivalent mutants. Sent for an independent review. |
| 2026-10-03 | PR2 | `029A` (the trading seams) built; review round 1 found 2 blocking and 3 should-fix, all fixed; round 2 PASS. PR #320 merged by the user on 2026-10-04. |
| 2026-10-04 | PR3 | `029G` (the bot chart): the desks' live chart moved into support behind `ICandleFeed`, `PriceLevelLayer`, the Grid overlay, one drawer and `BotChart` for the three surfaces. Two review rounds; PR #321 merged by the user. |
| 2026-10-04 | PR4 | `029E` (the live Grid executor): the actor, the level FSM, start, fills, pause, stop, SL/TP, HALTED and resume, reconciliation. Two fake-exchange journeys in the composed app found two fee defects; a Binance rules and failure review (the user's request) found four more; all six fixed with tests. Sent for an independent review. |
| 2026-10-04 | PR5 | `029F` (the Bots tab): the list, the detail shell, the Grid editor judged by the kind, New bot / Stop / Delete dialogs, one action at a time with fenced reads, the close guard (O4), a bot's orders and fills, `SPEC-014`. Sent for an independent review. |
| 2026-10-04 | PR6 merged, PR7 | `029D` merged after three review rounds. PR7: `029H`'s gated Spot Testnet grid round trip, the rate-limit read, and the Bots tab driving the real executor on the fake exchange. The user's first `-TestnetOnly` run: Spot passed, the Futures key was rejected (`-2015`). |
| 2026-10-04 | PR6 | `029D` (the Grid backtest): a pure simulator through the live executor's reactions under the stated fill rule, the query over stored candles and streamed 1-second klines, the Backtest tab with cancel, fencing and a sync offer. Sent for an independent review. |

---

## 4. Blockers & Dependencies

| Blocker / Dependency | Impacted Tasks | Resolution / Owner | Status |
| :--- | :--- | :--- | :--- |
| ADR D6 changes a safety gate; D21 keeps one (O5); O1 adds configuration | 029A, and everything after it | The user, 2026-10-03: D6 own budget, O5 cap kept and configurable, O1 accepted | ✅ Resolved |
| O2 (resuming after Halted), O3 (stop default) | 029E | The user, 2026-10-03: accepted as proposed | ✅ Resolved |
| O4 (warning on app close) | 029F | The user, 2026-10-03: accepted as proposed | ✅ Resolved |
| Spot Testnet keys on the user's machine | 029H | The user (keys are never pasted into chat) | 🟡 Open |

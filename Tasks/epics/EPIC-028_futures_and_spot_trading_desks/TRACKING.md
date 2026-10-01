# EPIC-028 — Tracking

- **Epic:** [EPIC-028 — Two trading desks](README.md)
- **Status:** 🟡 In Progress — ADR accepted 2026-09-29; Phase 1 done (`028A`–`028C`); Phase 2: `028D`–`028F` merged, `028G` in review (PR #300)
- **Target Completion:** not committed; the bars below are relative estimates from the day the ADR is accepted.
- **Renders:** GitHub Markdown, VS Code Mermaid preview, or mermaid.live.

---

## 1. Schedule (Gantt)

Phase 2 can start as soon as `EPIC-028B` lands; Phase 3's UI can be built against fakes in parallel
with Phase 2's adapters.

```mermaid
gantt
    title EPIC-028 - Two trading desks
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m
    todayMarker stroke-width:2px,stroke:#d33,opacity:0.6

    section Spec
    Survey, ADR and sub-tasks              :done,    s1, 2026-09-29, 1d
    User decision on ADR D1-D8, O1-O5      :done,    s2, after s1, 2d

    section Phase 1 - Both venues in one process
    028A VenueContext and registry         :crit, done, a, after s2, 1d
    028B Venue-addressed commands          :crit, done, b, after a, 1d
    028C Both venues concurrently          :crit, done, c, after b, 1d
    Phase 1 exit check                     :milestone, m1, after c, 0d

    section Phase 2 - Account data
    028D Account summary                   :done,    d, after c, 1d
    028E Open orders and history           :done,    e, after d, 1d
    028F Commission, leverage, margin      :done,    f, after e, 1d
    028G Estimate policies                 :active,  g, after f, 1d
    Phase 2 exit check                     :milestone, m2, after g, 0d

    section Phase 3 - Shared desk kit
    028H Order entry core and Spot         :         h, after g, 4d
    028I Futures order entry variant       :crit,    i, after h, 4d
    028J Account tabs and summary          :         j, after e, 3d
    Phase 3 exit check                     :milestone, m3, after i, 0d

    section Phase 4 - Two desks
    028K Futures desk                      :         k, after m3, 2d
    028L Spot desk                         :         l, after m3, 2d
    028M Retire old screen, docs           :         mm, after k, 2d
    028N Dual-venue Testnet tier           :         n, after l, 1d
    Phase 4 exit check                     :milestone, m4, after mm, 0d
```

---

## 2. Sub-tasks & PR Matrix

| Id | Sub-task | Branch / PR | Risk | Status | Target / Merged |
| :--- | :--- | :--- | :-: | :--- | :--- |
| EPIC-028A | [VenueContext and registry](completed/EPIC-028A_venue_context_and_registry.md) | `claude/wizardly-cerf-fc5b5x` | 🔴 | ✅ Done | [#293](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/293) merged 2026-09-29 |
| EPIC-028B | [Venue-addressed commands](completed/EPIC-028B_venue_addressed_commands.md) | `claude/wizardly-cerf-fc5b5x` | 🔴 | ✅ Done | [#294](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/294) merged 2026-09-29 |
| EPIC-028C | [Both venues concurrently](completed/EPIC-028C_both_venues_running_concurrently.md) | `claude/wizardly-cerf-fc5b5x` | 🟡 | ✅ Done | [#295](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/295) merged 2026-09-30 |
| EPIC-028D | [Account summary](completed/EPIC-028D_account_summary_reader.md) | `claude/wizardly-cerf-fc5b5x` | 🟡 | ✅ Done | [#296](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/296) merged 2026-09-30 |
| EPIC-028E | [Open orders and history](completed/EPIC-028E_open_orders_and_history_readers.md) | `claude/wizardly-cerf-fc5b5x` | 🟡 | ✅ Done | [#297](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/297) merged 2026-09-30 |
| EPIC-028F | [Commission, leverage, margin](completed/EPIC-028F_commission_and_futures_account_controls.md) | `claude/wizardly-cerf-fc5b5x` | 🟡 | ✅ Done | [#299](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/299) merged 2026-09-30 |
| EPIC-028G | [Estimate policies](incomplete/EPIC-028G_order_estimate_policies.md) | `claude/wizardly-cerf-fc5b5x` | 🟢 | 🟡 In review | [#300](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/300) |
| EPIC-028H | [Order entry core and Spot](incomplete/EPIC-028H_order_entry_panel_core_and_spot.md) | — | 🟡 | 🔵 Planned | — |
| EPIC-028I | [Futures order entry](incomplete/EPIC-028I_futures_order_entry_variant.md) | — | 🔴 | 🔵 Planned | — |
| EPIC-028J | [Account tabs and summary](incomplete/EPIC-028J_account_tabs_and_summary_panels.md) | — | 🟡 | 🔵 Planned | — |
| EPIC-028K | [Futures desk](incomplete/EPIC-028K_futures_desk_screen.md) | — | 🟡 | 🔵 Planned | — |
| EPIC-028L | [Spot desk](incomplete/EPIC-028L_spot_desk_screen.md) | — | 🟢 | 🔵 Planned | — |
| EPIC-028M | [Retire old screen, docs](incomplete/EPIC-028M_retire_single_trading_screen_and_docs.md) | — | 🟢 | 🔵 Planned | — |
| EPIC-028N | [Dual-venue Testnet tier](incomplete/EPIC-028N_dual_venue_testnet_tier.md) | — | 🟡 | 🔵 Planned | — |

---

## 3. Milestone & Status Log

| Date | Item | Event & Outcome |
| :--- | :--- | :--- |
| 2026-09-29 | EPIC-028A | Merged in PR #293 after the independent review (four fixes: per-part lock, single-venue reader follows the list, guard sees every spelling, docs). |
| 2026-09-30 | EPIC-028G | Implemented, then redesigned after the PR #300 review: Futures cost and maximum by Binance's rules (assuming price, open loss, notional headroom), Spot by notional plus fee, a liquidation estimate typed as an estimate. Re-review PASS. |
| 2026-09-30 | EPIC-028F | Merged in PR #299 after two independent reviews: NEEDS_REVISION (the position read leaked SDK errors; fixed by moving it onto the port), then PASS. |
| 2026-09-30 | EPIC-028F | Implemented: `IFuturesAccountControl` (none on Spot), `ICommissionRateReader`, leverage and margin-mode commands behind one gate, commission-rate query. Fast tier green; awaiting independent review. |
| 2026-09-30 | EPIC-028E | Merged in PR #297 after two independent reviews: NEEDS_REVISION (a catalog download per unlisted Spot asset, fixed by `ListedSymbols`; 30-day lookback bound), then PASS (the fake enforces the lookback; aggregate weight cost moved to 028J). |
| 2026-09-30 | EPIC-028E | Implemented: `IAccountHistoryReader` per venue, never-truncated window splitting, open-orders/order-history/trade-history queries, Spot average entry price. Fast tier green; awaiting independent review. |
| 2026-09-30 | EPIC-028D | Merged in PR #296 after independent review (PASS); review fixes (stale-summary fence, SPEC-003, ADR D6, warn-once) landed before merge. |
| 2026-09-30 | EPIC-028D | Implemented: `AccountSummary` on the existing connection check (no new port), `GetAccountSummaryQuery`, per-venue refresh on cadence and on fill, CLI available balance. Fast tier green; awaiting independent review. |
| 2026-09-30 | EPIC-028C | Merged in PR #295 after independent review (PASS); Phase 1 done. EPIC-028D started. |
| 2026-09-29 | EPIC-028C | Implemented: per-venue refresh + venue on events; Settings toggles; per-market stream and tick routing; per-venue saved strategy. Fast tier green; awaiting independent review. |
| 2026-09-29 | EPIC-028B | Implemented: commands/queries name their venue; `VenueTradingScopes`/`IVenueTradingPorts`/`VenueStrategySessions`; single-venue bindings deleted, guard added. Fast tier green; awaiting independent review. |
| 2026-09-29 | EPIC-028A | Implemented: `IVenueContexts` + per-venue `VenueAssembly`; single-venue ports are primary-venue shims. Fast tier green; awaiting independent review. |
| 2026-09-29 | ADR | Accepted by the user — D1–D8, O1–O5 per recommendation; `EPIC-028A` started. |
| 2026-09-29 | Spec | Epic scaffolded from a survey of `faf4a337`; ADR D1–D8 proposed, O1–O5 open; 14 sub-tasks in four phases. |

---

## 4. Blockers & Dependencies

| Blocker / Dependency | Impacted Tasks | Resolution / Owner | Status |
| :--- | :--- | :--- | :--- |
| ADR D1–D8 accepted, O1 answered | all | the user | ✅ Resolved 2026-09-29 |
| O2 Spot TP/SL, O3 stop-limit | EPIC-028H, EPIC-028I | the user | ✅ Resolved 2026-09-29 |
| O4 retire the old route, O5 history depth | EPIC-028E, EPIC-028M | the user | ✅ Resolved 2026-09-29 |
| Spot OCO protective orders | Spot TP/SL (out of scope) | `EPIC-026K` | 🟡 Open |

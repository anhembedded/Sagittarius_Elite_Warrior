# EPIC-025 — Tracking (Gantt)

- **How to read it.** One bar per pull request or review; `done` is merged, `active` is being
  worked, `crit` marks a review or a hands-on check that only the user can do, `milestone` marks
  a phase closing. Dates after today are **planning estimates**, revised every time a bar closes —
  HLD §6.4 says only Phase 0 can be estimated before Phase 0 has run, and the Phase 1+ bars will be
  re-cut when Phase 0's measurements are in.
- **Who updates it.** The executor (the EPIC-025 skill, checklist step 11) moves a bar to `done`
  in the same pull request that closes it, and re-dates the following bars if the estimate moved.
- **Renders** on GitHub, in VS Code with a Mermaid extension, or at mermaid.live.

```mermaid
gantt
    title EPIC-025 — module split on the Engine's IExtension microkernel
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m
    todayMarker stroke-width:2px,stroke:#d33,opacity:0.6

    section Spec
    Round 1 — HLD, ADR, EPIC scaffold           :done,    s1, 2026-09-10, 2026-09-11
    Round 2 — doctrine, workbench rule, SDD     :done,    s2, 2026-09-12, 2026-09-13
    Independent review + round 3               :done,    s3, 2026-09-13, 1d
    D17 sizing, D18/D19 tests, executor skill  :done,    s4, 2026-09-13, 1d
    User review of the spec                    :crit, active, s5, 2026-09-14, 2d

    section Phase 0 — mechanism + market_data (EPIC-025A)
    PR 0.1 baselines and guards                :         p01, after s5, 2d
    User review 0.1 (allowlist, golden master) :crit,    r01, after p01, 1d
    PR 0.2 core/ shell/ mechanism              :         p02, after r01, 3d
    User check 0.2 (app opens as before)       :crit,    r02, after p02, 1d
    PR 0.3 support/binance_gateway             :         p03, after r02, 1d
    PR 0.4 modules/market_data + contract suites + Data Management in QtWidgets : p04, after p03, 6d
    User check 0.4 (Data Management, CLI sync) :crit,    r04, after p04, 1d
    PR 0.5 skeleton walks with N=2             :         p05, after r04, 1d
    Phase 0 measured, Phases 1–5 re-estimated  :milestone, m0, after p05, 0d

    section Engine track
    E0 ScheduledJob.cancel()                   :         e0, after s5, 1d
    E1 lift module base + registry (after Phase 1) :     e1, after m1, 3d
    E2 lift surface runtime (after Phase 2)    :         e2, after m2, 3d
    E3 NavigationService, lifecycle, conformance :       e3, after p5, 5d

    section Phase 1 — trading + surfaces (EPIC-025B)
    Welcome surface, dev.mode gate, restart    :         p1a, after m0, 3d
    modules/trading, lease, panels, Order dialog :       p1b, after p1a, 7d
    Trading + Dev Board become QMainWindow modes, 59→0 : p1c, after p1b, 5d
    User runs Testnet (orders, cancel, PnL)    :crit,    r1, after p1c, 2d
    Phase 1 closed                             :milestone, m1, after r1, 0d

    section Phase 2 — strategy (EPIC-025C)
    modules/strategy, ISizingPolicy, per-symbol session : p2, after m1, 5d
    User runs Testnet (arm, disarm, tick→order) :crit,   r2, after p2, 2d
    Phase 2 closed                             :milestone, m2, after r2, 0d

    section Phase 3 — backtesting (EPIC-025D)
    modules/backtesting, 11 modals → QDialog, golden master : p3, after m2, 8d
    Phase 3 closed                             :milestone, m3, after p3, 0d

    section Phase 4 — support/*, ui/common dissolved (EPIC-025E)
    charting, indicators, ui_kit; Settings dialog; qml/ deleted : p4, after m3, 5d
    User review: designed theme? (D21 deferred)  :crit,    r4, after p4, 1d
    Phase 4 closed                             :milestone, m4, after r4, 0d

    section Phase 5 — Engine navigation (EPIC-025F)
    ScreenRegistry → NavigationService         :         p5, after m4, 4d
    Conformance suite on every surface         :         p5b, after e3, 2d
    EPIC-025 done                              :milestone, m5, after p5b, 0d
```

## Status log

| Date | Bar | Event |
| :--- | :--- | :--- |
| 2026-09-11 | s1 | Round 1 merged (PR #196) |
| 2026-09-13 | s2, s3, s4 | Rounds 2–3, D17–D19, executor skill merged (PRs #197–#205) |
| 2026-09-13 | — | ADR D20–D22 (QtWidgets only, OS theme, panels and dialogs): Phase 0/1/3 bars re-cut |

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
    User review of the spec                    :crit, done, s5, 2026-09-13, 1d

    section Phase 0 — mechanism + market_data (EPIC-025A)
    PR 0.1 baselines and guards                :done,    p01, 2026-09-13, 1d
    User review 0.1 (allowlist, golden master) :crit, done, r01, 2026-09-13, 1d
    PR 0.2 core/ shell/ mechanism              :done,    p02, 2026-09-13, 1d
    User check 0.2 (app opens as before)       :crit, done, r02, 2026-09-14, 1d
    PR 0.3 support/binance_gateway             :done,    p03, 2026-09-14, 1d
    PR 0.4a modules/market_data behind its UI    :active,  p04a, 2026-09-14, 4d
    PR 0.4b Data Management in QtWidgets        :         p04b, after p04a, 3d
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
| 2026-09-13 | s5, p01 | User approved the spec; Phase 0 started with PR 0.1 |
| 2026-09-13 | p01 | PR 0.1 built locally: 3 guards in `tests/unit/architecture/`, allowlist (10 pairs), QML baseline (35), golden master (13 trades), 3948 → 4059 tests collected; self-review split the guards into one file per abstraction level (architecture-rule §5); waiting for the user's review before push |
| 2026-09-13 | r01 | Review 0.1: the user pointed at the decision doctrine (§7) instead of answering; both questions settled by it in `EPIC-025A` §1.1 — allowlist as found, dataset stays generated. The pull request itself still waits for the user's push OK |
| 2026-09-13 | p02 | PR 0.2 built locally: theme layer's global sheet removed (ADR D21a), `core/` + `shell/` with the contribution mechanism, one ConfigManager, the five legacy screens as contributions, two new architecture guards; gate green, 4 153 tests |
| 2026-09-14 | r02 | PR 0.2 merged (PR #210) into master-warrior; work branch fast-forwarded. Phase 0 mechanism is in main; next is PR 0.3 (support/binance_gateway) |
| 2026-09-14 | p03 | PR 0.3 (PR #211): `support/binance_gateway` extracted — 9 modules and 6 tests moved; boundary allowlist 10 → 8 pairs, the epic's first retired entries; `exchange_session_factory` and `binance_error_translator` deferred with reasons (EPIC-025A §1.3) |
| 2026-09-14 | p03, p04 | PR 0.3 merged (PR #211); `src/src`, a dangling symlink committed by accident in `8dc9b3ef`, deleted (PR #212). PR 0.4 split into 0.4a (the module, behind the existing UI) and 0.4b (Data Management in QtWidgets) — two different kinds of risk, EPIC-025A §1.4; 0.4a started |
| 2026-09-14 | p04a | PR 0.4a + 0.4a-2 + 0.4a-3 pushed into PR #213 (8 commits, gate green): `modules/market_data` registered in `shell/modules.py`; CLI parsing inverted so the shell parses once and the module owns `sync`/`stream`; contract suites and verified fakes for `ISymbolCatalogRepository` and `IMarketDataRepository`, which deleted 253 lines of hand-rolled in-memory duplicates. Two bugs found and fixed on the way (BUG-118 leaked Qt objects, BUG-119 an endless `while True` the gate could not report), and `pytest-timeout` installed so a hang fails loudly. Allowlist 41 → 38 |
| 2026-09-14 | p04b | PR 0.4b-1 built locally, gate green (4 286 tests, coverage 95.09%): Data Management's last two QML islands rebuilt as a `QTableView` panel with the app's first four `QAction`s and a kline-inspector `QDialog`; 4 `.qml` files deleted, QML baseline 35 → 31, `Theme.*` bindings 229 → 204, net -1 128 lines. The spec's list of which four widgets was wrong and is corrected in EPIC-025A §1.7 (the time-range and timeframe pickers are shared with four other screens). Two guards written under the pre-ADR doctrine were answered with their own `base-exempt` hatch rather than a raised ceiling. Two questions left for the user: the unreachable integrity audit, and jump-to-date. Waiting for the push OK |
| 2026-09-14 | p04b | 0.4b-2 (move the screen into `modules/market_data/ui/`) **deferred to Phase 4**, measured rather than judged: 8 forward allowlist entries would be traded for 35 backward ones, and the epic's zero-backward-imports property would become 35. A module's `ui/` may import `support/ui_kit`/`support/charting` whole (HLD §6.1) and neither exists before Phase 4, which is where eight of the nine import groups are heading anyway. Recorded in EPIC-025A §1.8, carried into EPIC-025E step 6, and the 8 allowlist entries re-keyed to Phase 1 |

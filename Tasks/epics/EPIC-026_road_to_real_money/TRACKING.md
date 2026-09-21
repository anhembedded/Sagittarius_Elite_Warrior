# EPIC-026 — Tracking (Kanban, dependency graph, Gantt)

- **How to read it.** One card per sub-task on the Kanban; one bar per sub-task or per hands-on
  step on the Gantt. `crit` marks a step only the user can do (a decision, a Testnet or
  TradingView run, an independent review, a capital decision); `milestone` marks a gate. Every
  date after 2026-09-20 is a **planning estimate**, revised in the pull request that closes a bar.
- **Who updates it.** The executor of a sub-task moves its card and its bar in the same pull
  request that closes it, and re-dates the bars after it if the estimate moved
  (`report-task-rule.md`: the board is generated from the records, never hand-maintained apart).
- **Validated** with `@mermaid-js/mermaid-cli@11.17.0` on 2026-09-20 (exit 0, fresh SVG, per
  `.claude/skills/execute-task/references/mermaid-validation.md`); the sources below are the
  validated ones, unedited.
- **Renders** on GitHub, in VS Code with a Mermaid extension, or at mermaid.live.

## 1. Kanban (2026-09-20)

```mermaid
kanban
  todo[To do]
    a[EPIC-026A - SPEC-006 cancel one open order]
    b[EPIC-026B - SPEC-007 Emergency Stop]
    c[EPIC-026C - SPEC-010 arm and disarm]
    d[EPIC-026D - edge thresholds decision]
    e[EPIC-026E - rolling walk-forward validation]
    f[EPIC-026F - live candidate report]
    g[EPIC-026G - trade journal]
    h[EPIC-026H - crash recovery adopts journaled positions]
    i[EPIC-026I - resilient submission]
    j[EPIC-026J - leverage and margin type set on exchange]
    k[EPIC-026K - exchange-side protective stop]
    l[EPIC-026L - daily-loss circuit breaker]
    m[EPIC-026M - out-of-band alerting]
    n[EPIC-026N - user-data-stream watchdog]
    o[EPIC-026O - reconciliation script and soak report]
    p[EPIC-026P - FUTURES_MAINNET member and factory parameter]
    q[EPIC-026Q - mainnet caps and typed acknowledgement]
    r[EPIC-026R - mainnet read-only first contact]
    s[EPIC-026S - live-versus-backtest report]
  doing[In progress]
  blocked[Blocked]
    pro[PRO-005 and ADR - awaiting the user's decision on O1-O4]
  verifying[Awaiting verification or review]
  done[Done]
```

## 2. Dependency graph — the gates are the critical path

Stage 1 and stage 2 are independent (ADR D2). Stage 3 needs both gates and the accepted ADR.
Stage 4 is a loop: run a capital stage, report, decide.

```mermaid
flowchart LR
  classDef gate fill:#3d3410,stroke:#c9a227,color:#fdf3d0
  classDef user fill:#3d1f1f,stroke:#c96a6a,color:#fadada

  subgraph S0["Stage 0 - close the open specs"]
    A["A SPEC-006"]
    B["B SPEC-007"]
    C["C SPEC-010"]
    U025["User: EPIC-025B/C Testnet run"]:::user
  end
  subgraph S1["Stage 1 - prove the edge"]
    D["D thresholds (O1)"]:::user
    E["E walk-forward"]
    F["F candidate report"]
    U001["User: EPIC-001B TradingView diff"]:::user
  end
  subgraph S2["Stage 2 - operations, soaked on Testnet"]
    G["G journal"]
    I["I resilient submission"]
    H["H crash recovery (O2)"]
    J["J leverage set on exchange"]
    K["K protective stop"]
    L["L circuit breaker"]
    M["M alerting (O4)"]
    N["N stream watchdog"]
    O["O reconciliation + 14-day soak"]
  end
  subgraph S3["Stage 3 - mainnet, locked"]
    ADR["ADR accepted (D3-D5, O3)"]:::user
    P["P FUTURES_MAINNET member"]
    Q["Q caps + typed acknowledgement"]
    R["R read-only first contact"]
    REV["Independent review of P"]:::user
  end
  subgraph S4["Stage 4 - staged capital"]
    S["S live-vs-backtest report"]
    CAP["User: next capital decision"]:::user
  end

  U025 --> C
  A --> G1{{"Gate 0"}}:::gate
  B --> G1
  C --> G1
  D --> E --> F
  U001 --> F
  F --> G2a{{"Gate 1"}}:::gate
  G --> H
  G --> K
  I --> K
  I --> J
  G --> L
  M --> N
  H --> O
  J --> O
  K --> O
  L --> O
  N --> O
  O --> G2b{{"Gate 2"}}:::gate
  G1 --> G
  G1 --> I
  G1 --> M
  G2a --> P
  G2b --> P
  ADR --> P
  P --> REV --> Q
  P --> R
  Q --> G3{{"Gate 3"}}:::gate
  R --> G3
  G3 --> S --> CAP --> S
```

## 3. Gantt — planning estimates

The critical path is stage 2's 14-day soak, not stage 1. Working days are the unit; a `1d` bar is
one pull request of the size `EPIC-021`'s tasks had (each closed in under a day of work).

```mermaid
gantt
    title EPIC-026 - from Futures Testnet to real money, five gated stages (planning estimates, 2026-09-20)
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m
    todayMarker stroke-width:2px,stroke:#d33,opacity:0.6

    section Decision
    PRO-005 and ADR written                    :done,    pro, 2026-09-20, 1d
    User decides direction and O1-O4           :crit,    dec, 2026-09-22, 2d

    section Stage 0 - close the open specs
    User confirms EPIC-025B/C on Testnet       :crit,    u025, 2026-09-22, 2d
    A SPEC-006 cancel one open order           :         a, after dec, 1d
    B SPEC-007 Emergency Stop                  :         b, after a, 1d
    C SPEC-010 arm and disarm                  :         c, after b, 1d
    Gate 0 passed                              :milestone, g0, after c, 0d

    section Stage 1 - prove the edge
    D thresholds fixed (O1)                    :crit,    d, after dec, 1d
    User runs EPIC-001B TradingView diff       :crit,    u001, after d, 3d
    E rolling walk-forward validation          :         e, after d, 3d
    F candidate report                         :         f, after e u001, 2d
    Gate 1 passed                              :milestone, g1, after f, 0d

    section Stage 2 - operations, soaked on Testnet
    G trade journal                            :         g, after g0, 3d
    I resilient submission                     :         i, after g0, 2d
    M out-of-band alerting (O4)                :         m, after g0, 2d
    H crash recovery (O2)                      :         h, after g, 2d
    J leverage set on exchange                 :         j, after i, 1d
    K exchange-side protective stop            :         k, after g i, 3d
    L daily-loss circuit breaker               :         l, after k, 2d
    N user-data-stream watchdog                :         n, after m, 2d
    O reconciliation script                    :         o1, after h j l n, 1d
    O 14-day unattended Testnet soak           :crit,    o2, after o1, 14d
    O soak report, drills, reconciliation      :         o3, after o2, 1d
    Gate 2 passed                              :milestone, g2, after o3, 0d

    section Stage 3 - mainnet, locked
    P FUTURES_MAINNET member and factory       :         p, after g1 g2, 2d
    Independent review of P                    :crit,    rev, after p, 1d
    Q caps and typed acknowledgement (O3)      :         q, after rev, 2d
    R read-only first contact on mainnet       :crit,    r, after rev, 1d
    Gate 3 passed                              :milestone, g3, after q r, 0d

    section Stage 4 - staged capital
    Capital stage 1 runs (user-sized)          :crit,    s1, after g3, 14d
    S live-versus-backtest report              :         s, after s1, 1d
    User decides increase, hold or stop        :crit,    cap, after s, 1d
```

## 4. Estimate, in calendar terms

| Stage | Earliest start | Duration (estimate) | Gate |
| :--- | :--- | :--- | :--- |
| Decision | 2026-09-22 | 2 days of the user's time | — |
| 0 | 2026-09-24 | 3 pull requests, ~3 days | Gate 0 ≈ 2026-09-27 |
| 1 | 2026-09-24 | ~6 days, of which 3 are the user's TradingView run | Gate 1 ≈ 2026-09-30 |
| 2 | 2026-09-27 | ~9 days of pull requests, then a **14-day soak** and a day of drills | Gate 2 ≈ 2026-10-21 |
| 3 | 2026-10-21 | ~5 days including the independent review | Gate 3 ≈ 2026-10-26 |
| 4 | 2026-10-26 | 14 days per capital stage, repeated | per stage |

A first real-money fill, at the smallest stage, is therefore **the last days of October 2026** if
the decision lands in the week of 2026-09-22 and nothing in stage 2 uncovers a defect that the soak
must be restarted for. The soak restarts from zero after any fix to G–N; that is the one rule that
can move gate 2.

# EPIC-026 — From Futures Testnet to real money, through five gated stages

- **Status:** 🔵 Planned — awaiting the user's decision on [`PRO-005`](../../proposal/PRO-005.md)
  and the ADR's open questions O1–O4.
- **Repositories:** Elite. No Engine change is expected (every mechanism needed — ports, DI, event
  bus, feeds, scheduler — already exists, as `EPIC-021` found).
- **Origin:** [`PRO-005`](../../proposal/PRO-005.md) — the user (2026-09-20): *"đánh giá xem giờ
  phát triển thêm gì nữa? hãy cho lô trình để có thể giao dịch thật"* ("assess what to develop
  next; give a roadmap to be able to trade for real"), then *"biết tài liều cho hướng đi mới, gen
  grannt chart, chi nhỏ task"* ("write the documents for the new direction, generate a Gantt
  chart, split it into small tasks").
- **North star:** [`Docs/HLD/`](../../../Docs/HLD/README.md) for the module boundaries every
  sub-task respects (`trading` owns submission, limits and the lease; `strategy` owns sizing and
  the tick path; `binance_gateway` is the one anticorruption layer around the SDK). The
  operational design this epic adds is in the ADR below; when it is accepted, its decisions become
  a section of the HLD in the same pull request as `EPIC-026G`, not a second design document.
- **Decisions:** [`DECISION_2026-09-20_mainnet_venue.md`](DECISION_2026-09-20_mainnet_venue.md) —
  D1–D9, status Proposed; open questions O1–O4.
- **Tracking (Kanban, dependency graph, Gantt):** [`TRACKING.md`](TRACKING.md).
- **Dependencies:** the user's own Testnet confirmation that closes
  [`EPIC-025B`](../EPIC-025_module_theo_bounded_context/incomplete/EPIC-025B_phase1_trading_and_surfaces.md)
  and [`EPIC-025C`](../EPIC-025_module_theo_bounded_context/incomplete/EPIC-025C_phase2_strategy.md)
  (arm / disarm / tick → order); [`EPIC-001B`](../EPIC-001_ema_trend_pullback_tradingview_cross_reference/incomplete/EPIC-001B_run_and_diff_tradingview_vs_app_trade_lists.md)
  for stage 1; [`BOT-018`](../../backlog/BOT-018_notifications_alerting.md) is delivered by
  `EPIC-026M` rather than separately.

---

## 1. Decisions already made

None is accepted yet. The ADR proposes nine; the ones that shape the sub-task list are:

1. **Five gated stages** (D1): 0 close the open specs · 1 prove the edge · 2 harden operations and
   soak on Testnet · 3 open mainnet · 4 stage capital. A stage starts only when the previous gate is
   recorded as passed in §4 below.
2. **Stages 1 and 2 run in parallel** (D2); stage 3 waits for both.
3. **Mainnet is one reviewed enum member plus a factory parameter** (D3) — no flag, no override,
   no second path — with its own credential names (D4), a typed acknowledgement and smaller caps (D5).
4. **The operational half is soaked on Testnet for 14 unattended days** before mainnet exists in the
   code (D6).

## 1.1 What the tree already has (measured 2026-09-20, so nobody rebuilds it)

| Capability | Where |
| :--- | :--- |
| Signed sessions with a measured clock offset; Testnet hard-coded | `src/modules/trading/adapters/binance/futures_session_factory.py:45-72, 93, 113` |
| Rounding to lot step and tick, minimum notional refused before the network | `execute_order/handler.py:101-104`, `order_quantity_rounding_policy.py` |
| Four session limits, configurable thresholds | `domain/policies/trading_limit_policy.py:30-80`, `config_keys.py:83-92` |
| Symbol lease; one guard across evaluate → submit → record | `execute_order/handler.py:114-135` |
| Client order id on every order | `contracts/client_order_id.py`, `futures_order_payload_mapper.py` |
| Order truth from the user data stream; reconnect with generation fencing | `adapters/binance/futures_user_data_stream.py` |
| Reconciliation at enable; foreign positions refused | `session/enable_trading/handler.py:119-125` |
| Emergency Stop: disable → cancel all → close all, `LIVE` client allowed in two files only | `session/emergency_stop/handler.py`, `tests/unit/architecture/test_order_submission_mode_live_is_restricted.py` |
| Tick → signal → order, never through the shared bus | `strategy/application/services/live_trading_coordinator.py:7-22` |
| Opt-in real-Testnet tier | `tests/testnet/test_order_lifecycle.py` |

## 2. Goals — measurable

| Metric | Today (measured 2026-09-20) | When the epic is done |
| :--- | :-: | :-: |
| Reserved SPECs with code but no "Proven by" (`SPEC-006`, `007`, `010`) | 3 | 0 |
| Strategies with a written, threshold-judged candidate report | 0 | 1 |
| Trading facts that survive a restart (orders, fills, positions, breaker state) | 0 | all four, in one journal |
| Positions on the exchange the app cannot explain after a 14-day unattended Testnet run | not measurable (no journal) | 0 |
| Places `futures_change_leverage` is called | 0 | 1, on arm, read back |
| Entries without an exchange-side protective stop | every entry | 0 |
| PnL-based limits | 0 | daily loss and drawdown, both journaled |
| Channels that reach an operator who is not looking at the screen | 0 | 1 |
| `TradingVenue` members | 2 | 3, the third behind an ADR, a typed acknowledgement and its own credentials |
| Real-money stages with a live-versus-backtest report before the next increase | — | every one |

## 3. Sub-tasks, ordered by risk

Within a stage the order is by risk; the stages are the gates. `S` / `M` / `L` is the task file's
complexity; every task is one pull request unless its file says otherwise.

| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| **Stage 0 — nothing open behind us** | | | | | |
| [EPIC-026A](incomplete/EPIC-026A_spec_006_cancel_one_open_order.md) | `SPEC-006` — cancel one open order, written and proven | Elite | None | 🟢 | Planned |
| [EPIC-026B](incomplete/EPIC-026B_spec_007_emergency_stop.md) | `SPEC-007` — Emergency Stop, written and proven | Elite | None | 🟢 | Planned |
| [EPIC-026C](incomplete/EPIC-026C_spec_010_arm_and_disarm_a_strategy.md) | `SPEC-010` — arm a strategy on a symbol, and disarm it, written and proven | Elite | the user's `EPIC-025B`/`C` confirmation | 🟢 | Planned |
| **Stage 1 — the edge is real** | | | | | |
| [EPIC-026D](incomplete/EPIC-026D_edge_thresholds_decision.md) | The acceptance thresholds for a live candidate, fixed before any run (ADR O1) | Elite | None (user decision) | 🟢 | Planned |
| [EPIC-026E](incomplete/EPIC-026E_rolling_walk_forward_validation.md) | Rolling walk-forward validation over stored history, on the existing out-of-sample split | Elite | D | 🟡 | Planned |
| [EPIC-026F](incomplete/EPIC-026F_live_candidate_report.md) | The candidate report: one strategy, one symbol, one timeframe, judged against D | Elite | E, `EPIC-001B` | 🟡 | Planned |
| **Stage 2 — operations survive without a human** | | | | | |
| [EPIC-026G](incomplete/EPIC-026G_trade_journal.md) | Trade journal: orders, fills, positions and breaker state in SQLite | Elite | None | 🔴 | Planned |
| [EPIC-026I](incomplete/EPIC-026I_resilient_submission.md) | Resilient submission: explicit `recvWindow`, timeout resolved by client order id, backoff on rate limits | Elite | None | 🔴 | Planned |
| [EPIC-026H](incomplete/EPIC-026H_crash_recovery_adopt_journaled_positions.md) | Crash recovery: a position the journal recorded as ours is adopted on enable (ADR O2) | Elite | G | 🔴 | Planned |
| [EPIC-026J](incomplete/EPIC-026J_leverage_and_margin_type_set_on_exchange.md) | Leverage and margin type set on the exchange on arm, and read back | Elite | I | 🟡 | Planned |
| [EPIC-026K](incomplete/EPIC-026K_exchange_side_protective_stop.md) | Exchange-side protective stop: reduce-only `STOP_MARKET` after each entry fill | Elite | G, I | 🔴 | Planned |
| [EPIC-026L](incomplete/EPIC-026L_daily_loss_circuit_breaker.md) | Daily-loss and drawdown circuit breaker that trips Emergency Stop and stays tripped | Elite | G | 🔴 | Planned |
| [EPIC-026M](incomplete/EPIC-026M_out_of_band_alerting.md) | Out-of-band alerting for trading events (delivers `BOT-018`; ADR O4) | Elite | None | 🟡 | Planned |
| [EPIC-026N](incomplete/EPIC-026N_user_data_stream_watchdog.md) | User-data-stream watchdog: silence alerts, an exhausted reconnect budget disables trading | Elite | M | 🔴 | Planned |
| [EPIC-026O](incomplete/EPIC-026O_reconciliation_script_and_soak_report.md) | Journal-versus-exchange reconciliation script, and the 14-day Testnet soak report | Elite | G–N | 🟡 | Planned |
| **Stage 3 — mainnet exists and is locked** | | | | | |
| [EPIC-026P](incomplete/EPIC-026P_mainnet_venue_member_and_factory_parameter.md) | `TradingVenue.FUTURES_MAINNET`, the factory parameter, separate credentials, the fourth alignment state (ADR D3, D4) | Elite | O, ADR accepted | 🔴 | Planned |
| [EPIC-026Q](incomplete/EPIC-026Q_mainnet_caps_and_typed_acknowledgement.md) | Mainnet caps with a hard ceiling, and a typed acknowledgement on enable (ADR D5, O3) | Elite | P | 🔴 | Planned |
| [EPIC-026R](incomplete/EPIC-026R_mainnet_read_only_first_contact.md) | Mainnet read-only first contact with a restricted key: `exchange-status`, permissions checked | Elite | P | 🟡 | Planned |
| **Stage 4 — capital is earned** | | | | | |
| [EPIC-026S](incomplete/EPIC-026S_live_versus_backtest_report.md) | Live-versus-backtest report after each capital stage; the next increase is a user decision | Elite | Q, R | 🟡 | Planned |

## 4. Phase exit criteria

| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| Stage 0 | `SPEC-006`/`007`/`010` are ✅ in `Docs/SPEC/README.md`; `EPIC-025` has nothing in `incomplete/` | `tests/unit/architecture/test_spec_index_is_consistent.py` green with the three files; the user's Testnet run recorded in `EPIC-025B`/`C`. Not run. |
| Stage 1 | One candidate passes O1's thresholds out of sample and on rolling windows; the TradingView diff has no unexplained trade | A dated report under `Tasks/reports/` (`EPIC-026F`); `EPIC-001B` moved to `completed/`. Not run. |
| Stage 2 | 14 unattended days on Testnet with the journal reconciled to the exchange at zero unexplained differences; every entry carried a stop; the breaker and the watchdog each fired at least once in a drill | The soak report (`EPIC-026O`) with the reconciliation script's output; the drill logs (`fix-bug-rule.md` §3's positive proof). Not run. |
| Stage 3 | `FUTURES_MAINNET` merged after an independent review; `exchange-status` against mainnet with a key that cannot withdraw | The reviewer's rubric comment on the `EPIC-026P` pull request; `EPIC-026R`'s output pasted into its task file. Not run. |
| Stage 4 | Each capital stage ends with a live-versus-backtest report and an explicit user decision to increase, hold or stop | `EPIC-026S`'s reports, one per stage. Not run. |

## 5. Out of scope

Spot and COIN-M; multi-symbol portfolios (the tick path is keyed by one live symbol by design,
`config_keys.py:98`); parameter optimisation (`BOT-108`); the backtest simulator's trailing and
break-even stops (`BOT-105`); backtest report persistence (`BOT-115`); the chart's tier-3 tools
(`BOT-011`). None of them shortens the path to a first real fill.

## Notes (newest first)

- **2026-09-20** — Epic, ADR, tracking and the nineteen sub-tasks written from the 2026-09-20
  survey of the tree; nothing accepted yet. Pull request to follow on
  `claude/brave-maxwell-fedzkm`.

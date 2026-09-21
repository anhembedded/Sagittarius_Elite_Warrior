# ADR — Real-money trading is reached through five gates, and mainnet becomes a venue member only behind the third

**Epic:** [`EPIC-026`](README.md)
**Date:** 2026-09-20
**Status:** Proposed
**Decided by:** Pending — the user, under `ONBOARDING.md` §7 (a real-money venue is a change of
direction and of the foundational safety type; neither is the agent's to decide). The agent's
part, labelled 🤖 below, is delegated design under the same section: named patterns, precedent in
this repository.
**Supersedes / superseded by:** extends, and does not reverse,
[`EPIC-021`'s ADR §3](../EPIC-021_ket_noi_binance_futures_testnet/DECISION_2026-09-01_moi_truong_san_va_duong_di_lenh.md)
("mainnet is not a configuration flip; it is a future epic that opens this enum file"). This is
that epic.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

## 1. Context

✅ The order path is real and Testnet-only by construction: `FuturesSessionFactory` passes
`testnet=True` at `src/modules/trading/adapters/binance/futures_session_factory.py:93` and `:113`;
`TradingVenue` has exactly `DISABLED` and `FUTURES_TESTNET`
(`src/support/binance_gateway/contracts/trading_venue.py:14-15`); `OrderSubmissionMode.LIVE` may be
constructed in two files, held by an AST guard
(`tests/unit/architecture/test_order_submission_mode_live_is_restricted.py:38-55`).

✅ Nothing about trading survives a restart (`trading_session_state.py:1-4`, by design), leverage
is never sent to the exchange (no `futures_change_leverage` in `src/`), no protective stop is
placed, no PnL-based limit exists, and no channel reaches an operator who is not looking at the
screen. `PRO-005` §1.2 has the table with evidence.

✅ The edge of the one reference strategy is unproven against its source (`EPIC-001B` not started);
the repository's own direction since 2026-08 is *trustworthy backtests first, real trading deferred*.

The forces, then: the user wants real trading; the safety mechanism that stops it is a type, and
the reviewed change of that type is the intended way in; the parts Testnet let the project skip
are exactly the parts that lose money when skipped; and the decision of *how much* risk to accept
at each step is the user's.

## 2. Decisions

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | Real-money trading is reached through **five gated stages** (0 close the open specs; 1 prove the edge; 2 harden operations and soak on Testnet; 3 open mainnet; 4 stage capital). A stage starts only when the previous gate is recorded as passed in the epic README §4. | 🔵 Proposed | Pending (user) | Longest calendar path of the three options in `PRO-005` §3; every gap is closed where failure is free. Precedent: `EPIC-021` §4, "ordered by increasing risk", read-only first contact before the first order. |
| D2 | Stages 1 and 2 are **independent** and run in parallel; stage 3 waits for both; stage 4 repeats per capital increase. | 🤖 Agent decision | delegated design | The Gantt's critical path is stage 2's soak, not stage 1's user-run comparison. |
| D3 | Mainnet enters the code as **one new enum member**, `TradingVenue.FUTURES_MAINNET`, plus a venue parameter on `FuturesSessionFactory`; **no** `allow_mainnet` flag, no environment-variable override, no second code path. The member is added in one pull request (`EPIC-026P`) whose review is by a different session. | 🔵 Proposed | Pending (user) | Keeps `EPIC-021` ADR §3's mechanism: the absence of the member was the lock; its reviewed presence is the key. `compute_venue_alignment` gains its fourth state (`venue_alignment.py:55` names this spot). |
| D4 | Mainnet credentials are **separate names** (`BINANCE_FUTURES_MAINNET_API_KEY` / `_SECRET`) resolved by the same env-first provider; a Testnet key can never be read as a mainnet key and vice versa. | 🤖 Agent decision | delegated design; the precedent is `EPIC-021B` §2.1's venue-scoped names (`env_first_credentials_provider.py:20-24`) | One more pair of names, zero ambiguity. |
| D5 | Enabling trading on mainnet requires a **typed acknowledgement** (the operator types the venue's name) and applies **mainnet-specific caps** that are smaller than Testnet's and cannot be raised above a hard ceiling from configuration. | 🔵 Proposed | Pending (user) — the ceiling values are the user's | The four existing limits stay; a fifth limit set, keyed by venue, is read by the same `TradingLimitPolicy`. Pattern: defence in depth on the one path every order takes (`execute_order/handler.py`). |
| D6 | Operational resilience (journal, recovery, resilient submission, leverage set on the exchange, protective stop, circuit breaker, alerting, watchdog) is built and **soaked on Testnet for 14 unattended days** before mainnet exists in the code. | 🔵 Proposed | Pending (user) | The soak is a gate with a measurable exit: a journal-versus-exchange reconciliation of zero unexplained differences (`EPIC-026O`). |
| D7 | The journal is **SQLite through SQLAlchemy** in its own file beside the kline vault, written from the user data stream and from submissions, read by recovery and by the circuit breaker. It is an adapter of `trading`; no other module reads it directly. | 🤖 Agent decision | delegated design; the precedent is `market_data`'s vault (`sqlalchemy_repository.py`) and the metadata cache | One storage technology, one ORM, already in `requirements.txt`. |
| D8 | The protective stop is an **exchange-side `STOP_MARKET`, reduce-only**, placed after each entry fill from the strategy's `stop_loss_pct`, cancelled on exit; it is *not* a client-side stop. | 🤖 Agent decision | delegated design; `OrderType.STOP_MARKET` already exists (`order_type.py:19`) and `ISizingPolicy` already carries `stop_loss_pct` (`i_sizing_policy.py:82`) | The position is protected while the app is dead, which a client-side stop cannot promise. |
| D9 | The circuit breaker trips an **Emergency Stop** (the existing command) and refuses re-enable for the rest of the UTC day; its state is journaled so a restart cannot reset it. | 🤖 Agent decision | delegated design; reuse of `EmergencyStopCommand` rather than a second close-everything path | One kill switch, two triggers (human, breaker). |

## 3. Alternatives considered

- **Add `MAINNET` now, trade small, fix what breaks.** Rejected: `EPIC-021` ADR §3 rejected the
  same shortcut, and every gap in `PRO-005` §1.2 would be met with capital at stake.
- **A client-side stop loss instead of D8.** Rejected: it protects nothing when the process is
  dead, which is the failure the stop exists for.
- **Persist the trading session state itself (enabled flag) across restarts.** Rejected: `EPIC-021G`
  §2.3 decided the switch is never remembered, and this ADR keeps that; the journal records what
  happened, not whether trading should be on.
- **A second `IOrderSubmission` implementation for mainnet.** Rejected: one path, one set of gates,
  one guard; the venue is a parameter of the session factory, not a second submission port.
- **Alerting through the UI only.** Rejected: the operator the alert is for is, by definition, not
  looking at the UI.

## 4. Open questions

| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | The acceptance thresholds for a live candidate: minimum out-of-sample profit factor, maximum drawdown, minimum trade count, minimum walk-forward windows passing. A risk-appetite decision. | Stage 1 (`EPIC-026D`) | 2026-09-20 |
| O2 | On restart with an open position the journal recorded as ours: adopt it (recommended — the strategy that planned the exit resumes) or refuse as today? | Stage 2 (`EPIC-026H`) | 2026-09-20 |
| O3 | The first mainnet stage: capital, leverage ceiling, notional cap per order, daily-loss cap. | Stage 3 (`EPIC-026Q`), stage 4 | 2026-09-20 |
| O4 | Alerting channel: Telegram (recommended, `BOT-018`'s own choice) or another. | Stage 2 (`EPIC-026M`) | 2026-09-20 |

## 5. Implementation evidence

| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1, D2 | [`README.md`](README.md) §3–§4, [`TRACKING.md`](TRACKING.md) | Not started | Not yet verified |
| D3, D4 | [`EPIC-026P`](incomplete/EPIC-026P_mainnet_venue_member_and_factory_parameter.md) | Not started | Not yet verified |
| D5 | [`EPIC-026Q`](incomplete/EPIC-026Q_mainnet_caps_and_typed_acknowledgement.md) | Not started | Not yet verified |
| D6 | [`EPIC-026O`](incomplete/EPIC-026O_reconciliation_script_and_soak_report.md) | Not started | Not yet verified |
| D7 | [`EPIC-026G`](incomplete/EPIC-026G_trade_journal.md) | Not started | Not yet verified |
| D8 | [`EPIC-026K`](incomplete/EPIC-026K_exchange_side_protective_stop.md) | Not started | Not yet verified |
| D9 | [`EPIC-026L`](incomplete/EPIC-026L_daily_loss_circuit_breaker.md) | Not started | Not yet verified |

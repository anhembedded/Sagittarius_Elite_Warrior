# EPIC-026G — Trade journal: every order, fill, position change and breaker state survives a restart

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.2 row 1; ADR D7; the user (2026-09-20):
*"hãy cho lô trình để có thể giao dịch thật"*.
**Risk:** 🔴 — a new adapter on the path every fill takes; a write that blocks the websocket
thread stalls order truth (`pitfalls/ui.md`, `async-ui-action-rule.md`).
**Complexity:** L — schema, adapter, two writers (submission, user data stream), one reader port,
migration of nothing (there is no prior state), and the thread-affinity proof.
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** updates `SPEC-004` §6 (the reconciled picture now has a local counterpart) and
`SPEC-005` §4.
**Depends on:** None

---

## 1. Context and problem

`src/modules/trading/application/trading_session_state.py:1-4`: "the in-memory record … deliberately
not persisted". `EquityCurveRecorder` keeps a bounded in-memory ring (`equity_curve_recorder.py:24-43`).
No table, file or repository under `src/modules/trading/` records an order, a fill or a position.
Consequences with real money: after a crash the app cannot say which position it opened (so
enable refuses, `enable_trading/handler.py:119-125`), a daily-loss limit (`EPIC-026L`) has nothing
to sum, and a reconciliation against the exchange (`EPIC-026O`) has nothing to compare.

## 2. Acceptance criteria

- [ ] A SQLite file `state/trading_journal.sqlite3` (path from config, beside the kline vault,
      gitignored like `state/`) with tables `orders`, `fills`, `position_changes`,
      `breaker_state`, each row carrying `venue`, `symbol`, `client_order_id` where applicable,
      `exchange_time`, `recorded_at`, and the raw event payload as JSON for forensics.
- [ ] `IOrderSubmission.submit(live=True)` records the *intent* before the network call and the
      *outcome* (sent / rejected / failed) after it, keyed by client order id; a crash between the
      two leaves an `intent` row with no outcome, which `EPIC-026I` and `EPIC-026H` treat as "ask
      the exchange".
- [ ] Every `ORDER_TRADE_UPDATE` and `ACCOUNT_UPDATE` the user data stream parses is journaled
      **before** its event is published, on a worker, never on the websocket thread — proven by
      the thread-affinity sanity pattern (`tests/sanity/test_view_model_thread_affinity_sanity.py`).
- [ ] `ITradeJournal` (port, `trading/contracts/`) exposes `open_positions_believed()`,
      `orders_since(day)`, `realised_pnl_since(day)`, `breaker_state()`; no other module imports
      the SQLAlchemy models.
- [ ] A verified fake `FakeTradeJournal` in `contracts/testing/` with the contract suite both
      implementations pass (`testing-rule.md`, HLD §10).
- [ ] A journal write failure is logged at `ERROR` under `App.TradeJournal` and **does not** drop
      the event; the run-log scan (`ci-rule.md` §3) therefore fails a gate where it happened.

## 3. Design

Pattern: the vault (`market_data/adapters/persistence/sqlalchemy_repository.py`) — SQLAlchemy,
WAL, one engine per process — reused, not copied: the session factory helper moves to
`infrastructure/persistence/` if it is not already shareable. Writers subscribe to the module's
own events (`OrderSubmittedEvent`, `OrderFilledEvent`, `PositionChangedEvent`,
`EquitySampledEvent`) through the engine's bus with `report_handler_failure`; the submission
handler writes its intent row directly (it is the one place that knows an order is about to
leave). Reads are synchronous and small. The port and DTOs are frozen; models never leave the
adapter (ADR D7).

The schema is versioned by a single `schema_version` table; the first version is 1 and a
mismatch refuses to start trading with a named reason, never migrates silently.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_trade_journal.py`, `journal_entries.py` | Port and DTOs |
| `src/modules/trading/contracts/testing/fake_trade_journal.py`, `contract_trade_journal.py` | Verified fake and contract suite |
| `src/modules/trading/adapters/persistence/sqlalchemy_trade_journal.py`, `journal_models.py` | Adapter |
| `src/modules/trading/application/journal/journal_event_writer.py` | Subscribes and writes on a worker |
| `src/modules/trading/application/orders/execute_order/handler.py` | Intent row before submit, outcome after |
| `src/modules/trading/composition/adapter_bindings.py`, `state_bindings.py` | Bindings |
| `src/config/config_keys.py`, `app_config.json` | `trading.journal_path` |
| `tests/unit/modules/trading/contracts/test_trade_journal_contract.py` and integration twin | Contract suite |
| `tests/unit/modules/trading/application/journal/test_journal_event_writer.py` | Worker, failure logged, event not dropped |
| `tests/integration/application/test_journal_against_fake_server.py` | Submit → fill → rows |
| `Docs/VOCABULARY/README.md` | Row: **Trade journal** |
| `Docs/HLD/03_module_contracts.md` | `trading` gains `ITradeJournal` (ADR D7 accepted) |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Contract | contract suite on fake and SQLite | unit + integration | both green |
| Not on the websocket thread | thread-affinity sanity pattern applied to the writer | sanity | green |
| Intent without outcome | unit test kills the client between the two writes | unit | one `intent` row, no outcome |
| Write failure | unit test with a failing engine | unit | `ERROR` logged, event still published |
| End to end | integration test against the fake server | integration | rows match the fake's fills |
| Gate | `ci-local.ps1 -Full` on GitHub; log grepped | full | no `ERROR` from `App.TradeJournal` |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)

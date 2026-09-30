# EPIC-028D — Each desk knows its available balance, wallet, margin and unrealized PnL (Futures) or free/locked and equity (Spot)

**Status:** ✅ Done (2026-09-30) — merged in PR #296 after an independent review (PASS)
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — Futures `walletBalance` is shown today as if it were spendable
**Complexity:** M — two value types, both readers, a query and a refresh (no new port; see Implementation notes)
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028B](../completed/EPIC-028B_venue_addressed_commands.md)

---

## 1. Context and problem
- `ExchangeConnectionStatus.usdt_balance` is Futures `walletBalance` (not `availableBalance`) and
  appears only in the CLI and Settings (`presentation/cli/exchange_status_formatter.py`).
- Spot equity exists (`SpotAccountReader._compute_equity`) but no screen shows it.

## 2. Acceptance criteria
- [x] `GetAccountSummaryQuery(venue)` returns an `AccountSummary`: Futures → available, wallet, margin balance, unrealized PnL, position mode; Spot → quote free/locked, equity (or `None` per EPIC-027H's never-guess rule).
- [x] The summary refreshes on the existing poll cadence and on every `OrderFilledEvent` of its venue.
- [x] `exchange-status` prints available balance for Futures.

## 3. Design
`IAccountSummaryReader` (ABC) with `FuturesAccountSummaryReader` (`futures_account` fields `availableBalance`, `totalMarginBalance`, `totalUnrealizedProfit`) and `SpotAccountSummaryReader` (reuses `SpotAccountReader`'s holdings/equity). Two value types, not one with `None` fields everywhere: `FuturesAccountSummary`, `SpotAccountSummary` behind a shared `AccountSummary` protocol for the common three figures.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_account_summary_reader.py`, `account_summary.py` | new |
| `src/modules/trading/adapters/binance/…account_summary_reader.py` (×2) | new |
| `src/modules/trading/application/queries/get_account_summary/` | new CQRS query |
| `src/presentation/cli/exchange_status_formatter.py` | available balance |

## 5. Testing
Unit per adapter against recorded payloads; fake-exchange integration for both venues.
- Unit, readers: `test_futures_account_reader.py` (summary from the USDT asset, hedge mode still summarised, no USDT asset → `None`, a malformed or missing figure → `None` plus a WARNING); `spot/test_spot_account_reader.py` (free/locked split, no quote holding → zeros, an unpriceable holding → `equity=None`).
- Unit, application: `queries/test_get_account_summary.py` (each venue answers from its own reader; unreadable → `None`); `test_account_summary_refresh_service.py` (disabled → no-op, first read publishes, unchanged → silent, changed → republished, `None` and a raised read → skipped, a fill on the venue hands a refresh to `run_elsewhere` instead of reading inline, another venue's fill asks nothing).
- Wiring: `test_module_venue_refresh_services.py` — `TradingModule.boot()` schedules each venue's summary refresh, and an `OrderFilledEvent` emitted on the container's real `MemoryEventBus` refreshes only its own venue's summary, through `IThreadManager`.
- CLI: `test_exchange_status_formatter.py` — the `Available (USDT)` line, and `?` without a summary.
- Integration (fake exchange): `test_futures_account_reader_against_fake_server.py` asserts the summary; `test_spot_manual_order_pipeline_against_fake_server.py` asserts a real BUY lowers the summary's available balance.
- Mutation: 18 mutations over the readers, service, boot wiring, composition, handler and formatter, each killed by the tests above.

## Implementation notes (written when done)
- **No new port — a deliberate deviation from §3.** Both `ITradingAccountReader` implementations already fetch the whole account payload for `check_connection()`; a second `IAccountSummaryReader` would sign and send the same request again and add a seventh member to `VenueContext`. Instead `ExchangeConnectionStatus` gained `summary: AccountSummary | None` (default `None`), filled by each reader from the payload it already holds, and `GetAccountSummaryQueryHandler` reads it off the addressed venue's reader — the seam `GetHoldingsQueryHandler` uses. A future venue adds a subclass of `AccountSummary` and fills it in its reader; nothing else changes.
- **Types.** `AccountSummary` (venue, available, equity) is a frozen base class, not a protocol: both subclasses are ours and a dataclass base keeps the common three figures typed. `FuturesAccountSummary` adds wallet, margin balance, unrealized PnL and position mode; `SpotAccountSummary` adds quote asset, free and locked. `equity` is `None` only when Spot cannot price a holding (EPIC-027H).
- **USDT asset, not account totals.** §3 named `totalMarginBalance`/`totalUnrealizedProfit`; the summary reads the USDT asset's `availableBalance`/`walletBalance`/`marginBalance`/`unrealizedProfit` instead, so every figure is in the quote asset the desk shows. The account-wide totals differ only for a multi-asset-margin account, recorded as a plausible extension in `account_summary.py`. A missing or non-numeric figure gives no summary and a WARNING, never an invented zero.
- **Refresh.** `AccountSummaryRefreshService` (one per enabled venue, `build_account_summary_refreshes`) runs on the existing account-refresh cadence and publishes `AccountSummaryChangedEvent` only when the summary changed, so an idle account does not repaint screens every 5 s. `OrderFilledEvent` arrives on the user-data stream's asyncio loop (`BOT-145`), so `on_order_filled` hands `refresh_once` to `run_elsewhere`, bound to `IThreadManager.submit` at composition.
- **Accepted cost: Spot reads its account twice per tick.** Holdings and summary each call `check_connection()`. Request weight stays far under Binance's limits; merging the two refreshes into one is the change if that ever matters.
- **Review follow-ups (PR #296, PASS with three should-fix items and two questions).**
  - *Race (should-fix 1).* The scheduler's tick and a fill's worker both run `refresh_once`; a tick whose request left before the fill could publish its pre-fill answer after the fill's refresh. Each refresh now takes a ticket when it starts, and a result older than the last one published is dropped (a fence, not a lock around the network call, so neither thread waits on the other's request). `test_a_tick_answering_after_a_later_fill_refresh_is_not_published` reproduces the reviewer's interleaving on one thread; red before, green after.
  - *SPEC-003 (should-fix 2)* describes the summary and the CLI's new lines; the Futures wallet line now reads `Wallet (USDT)` beside `Available (USDT)`.
  - *ADR D6 (should-fix 3)* carries a dated amendment recording the dropped port.
  - *Repeated WARNING (Q4).* `FuturesAccountReader` reports an unreadable summary once per outage (then DEBUG), and logs INFO when it is readable again; `test_a_lasting_malformed_figure_warns_once_until_it_is_readable_again`.
  - *Shared worker pool (Q5).* Accepted: a fill refresh that queues behind a backtest in the four-worker pool is no later than the next tick (5 s by default), which runs on the scheduler's own thread. A dedicated executor would be one more pool to size and shut down, for no user-visible gain. The pool keeps what a task raises on an unread `Future`, so the fill refresh now logs its own failure at ERROR (`test_a_failed_refresh_after_a_fill_is_logged_not_lost`).
- **Fake exchange.** `tests/sanity/fake_exchange/futures_routes.py`'s USDT asset now carries the four figures the real `/fapi/v2/account` returns.
- No screen shows the summary yet; `AccountSummaryChangedEvent` is the input the desk headers in `EPIC-028K`/`028L` consume.

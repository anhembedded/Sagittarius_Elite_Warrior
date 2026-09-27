# EPIC-027L — Spot order truth and balances come from the Spot user data stream

**Status:** ✅ Done (2026-09-27)
**Source:** follows the user's *"giao dịch spot"* request, 2026-09-26; `EPIC-021` ADR §4 ("order truth comes from the user data stream, not from the order response").
**Risk:** 🔴 — if the stream is wrong, every downstream screen, limit and emergency stop acts on false state.
**Complexity:** L — socket, parser, reconnect with generation fencing, balance feed, equity.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027H](EPIC-027H_spot_account_reader_and_holdings_model.md), [EPIC-027K](EPIC-027K_spot_trading_client_and_order_path.md)

---

## 1. Context and problem
- `FuturesUserDataStream` uses `bsm.futures_user_socket()` and handles only `ORDER_TRADE_UPDATE` and
  `ACCOUNT_UPDATE` (`adapters/binance/futures_user_data_stream.py:252,304-306`).
- The parser reads the Futures position array `"a"."P"` and the wallet balance `"a"."B"."wb"`,
  with a hard-coded `_QUOTE_ASSET="USDT"` (`user_data_event_parser.py:44,103-143`).
- Equity samples come only from Futures `ACCOUNT_UPDATE` (`futures_user_data_stream.py:364-375`).
- Spot's stream is `user_socket()` with `executionReport`, `outboundAccountPosition` and
  `balanceUpdate` — confirmed as the real `python-binance` entry point by reading
  `binance/ws/streams.py` directly (`BinanceSocketManager.user_socket()`, not
  `futures_user_socket()`), matching this repo's own "verified by reading its source" standard
  (`FuturesUserDataStream`'s own docstring for its Futures equivalent).

## 2. Acceptance criteria
- [x] A `SpotUserDataStream` implements `IUserDataStream`. Order status and fills come from
      `executionReport`; balances from `outboundAccountPosition`/`balanceUpdate`.
- [x] It reuses the reconnect with generation fencing already proven for Futures. A stale-generation
      event is ignored and logged.
- [x] Holdings and equity update from the stream. Nothing polls the account in a loop.
- [x] The fee reported in `executionReport` (`n`, `N`: amount and asset) is recorded with the fill.

## 3. Design
- The connection/reconnect mechanism (`ITaskManager.spawn`/`CancellationToken`, `BUG-094`'s
  generation fencing, `BUG-096`'s `{"e": "error"}` sentinel handling, `bsm.<x>_socket()` re-entry
  to revive the library's own reconnect budget) is duplicated verbatim into `SpotUserDataStream`
  rather than extracted into a shared helper — the two classes differ only in the socket method and
  in what constructs their `_run_stream()` needs (see §3.1). Extracting a helper now, with exactly
  two call sites and no third planned, would be an unrequested abstraction (`architecture-rule.md`
  §7.2.1 — a variant waits for a real second case; here there already are two, but they diverge on
  every axis that would make a shared helper's parameter list non-trivial: credentials-only vs.
  credentials+session-state+client-factory, one socket method vs. another). The parsers were kept
  fully separate from the start, per the task's own instruction: `spot_user_data_event_parser.py`
  parses a **flat** payload (`"S"`/`"o"`/`"X"`/`"q"` at the top level); Futures'
  `user_data_event_parser.py` parses the same concepts nested one level down under `"o"` — different
  wire shapes for the same concept, exactly the reasoning that module's own docstring already gives.

### 3.1 A smaller dependency set than Futures, by design
Spot has no position-reconciliation concept — `TradingSessionState`/`ITradingClientFactory` exist to
answer "is this account now flat", which only makes sense where leverage/positions exist (ADR D8:
`TradingVenue` has no Spot mainnet member, and Spot never opens a leveraged position). So
`SpotUserDataStream` takes neither. Equity comes from `ITradingAccountReader.check_connection()` —
the same authoritative Spot equity/holdings computation `EPIC-027H` already built — re-fetched on
every `outboundAccountPosition`/`balanceUpdate`, never derived from the stream's own balance deltas:
the exchange's REST answer is the source of truth, matching Futures' own "re-fetch, never trust a
streamed delta alone" principle (`FuturesUserDataStream._handle_account_update`'s own
`get_positions()` re-fetch), just applied to the Spot-appropriate source. `EquitySample`/
`IEquityCurve`/`EquitySampledEvent` are reused as-is, with `unrealized_pnl=Decimal(0)` — an honest
zero, not a fabricated one, since a Spot holding has no unrealized-PnL-from-leverage concept
separate from its already-computed equity figure.

### 3.2 Fixture fix: `SpotAccountState._emit_fill_events()` was missing two fields
The fake exchange's own `executionReport` (from `EPIC-027J`) was missing `"x"` (execution type) and
`"q"` (the order's own requested quantity) — both required for a faithful parser: `is_fill_execution`
needs `"x"` to distinguish a fill from a status-only update (matching Futures' own `is_fill_execution`
check on the equivalent field), and `Order.quantity` must read `"q"`, not the cumulative-filled `"z"`
(which would silently under-report a partial fill's real order size). Fixed at the fixture, not
worked around in the parser — `fix-bug-rule.md`'s "fix the mechanism" doctrine and
`testing-rule.md`'s "the network-boundary substitute must behave like the real thing" principle:
the fixture's own module docstring already claims its shapes are sourced from Binance's documented
API, so this correction makes that claim true rather than encoding a second, divergent contract in
the parser to compensate.

### 3.3 `OrderFilledEvent` gained an optional fee
`fee_amount: Decimal | None = None` / `fee_asset: str | None = None`, both defaulted so Futures'
existing (fee-less) call site stays valid unchanged — Futures does not currently populate a fee
either, so both venues leave it `None` unless a caller populates it; only the new Spot parser does.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/spot/spot_user_data_stream.py` | new — `IUserDataStream` for Spot |
| `src/modules/trading/adapters/binance/spot/spot_user_data_event_parser.py` | new — flat-payload Spot parser |
| `src/modules/trading/contracts/events/order_filled_event.py` | `fee_amount`/`fee_asset`, both optional |
| `src/modules/trading/composition/adapter_bindings.py` | `IUserDataStream` venue-branches to `SpotUserDataStream` for `SPOT_TESTNET` |
| `tests/sanity/fake_exchange/spot_account_state.py` | `_emit_fill_events()` now emits `"x"`/`"q"` (§3.2) |
| `tests/unit/modules/trading/adapters/binance/spot/test_spot_user_data_event_parser.py` | new — 17 tests |
| `tests/unit/modules/trading/adapters/binance/spot/test_spot_user_data_stream.py` | new — 14 tests |

## 5. Testing
- Unit: `test_spot_user_data_event_parser.py` (17 tests — full fill/partial/new-ack, unrecognized
  status/type/time-in-force fall back to `UNKNOWN`/`None` never raise, `is_fill_execution`,
  `fill_details` reads `"L"`/`"l"` not running totals, `fill_fee` reads `"n"`/`"N"` or `None`,
  `stream_event_captured_at`); `test_spot_user_data_stream.py` (14 tests — fill routing with fee,
  `NEW` ack does not publish, `outboundAccountPosition`/`balanceUpdate` both re-fetch equity and
  publish `EquitySampledEvent`, unavailable/unreachable equity records nothing, `DEBUG`-not-`INFO`
  logging (`BUG-095`), the `{"e": "error"}` reconnect sentinel (`BUG-096`), `ReadLoopClosed`
  reconnect, and `BUG-094`'s generation-fencing mid-stream). All green.
- Regression: `tests/unit/modules/trading` + `tests/unit/architecture` + `tests/integration` —
  1555 passed, 4 pre-existing skips, 0 failed (baseline 1525 + 30 new tests). `mypy src+scripts`
  unchanged at the pre-existing 584-error baseline. `ruff check`/`ruff format --check` clean.
- Integration: not added — the acceptance criteria are fully covered at the unit tier (parser +
  stream routing against the fake exchange's own corrected `executionReport` shape); a live
  fake-exchange-to-screen journey would duplicate `test_fake_exchange_spot_routes.py`'s existing
  fixture coverage without adding a new observable fact this task's criteria require.
- Full local gate (`ci-local.ps1 -Full`): not run locally — GitHub Actions' `ci-local.ps1 -Full`
  check run is the authority (`ci-rule.md` §1, user decision 2026-09-18); cited from the PR once
  green.

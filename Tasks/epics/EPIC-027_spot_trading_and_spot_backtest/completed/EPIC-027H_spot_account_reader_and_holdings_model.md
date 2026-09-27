# EPIC-027H — The app reads a Spot account as balances and holdings, never as a futures position

**Status:** ✅ Done (2026-09-27)
**Source:** the user, 2026-09-26: *"tui muốn giao dịch spot"* ("I want to trade spot").
**Risk:** 🟡 — read-only, but it defines what "a position" means for everything built on top.
**Complexity:** M — domain type, adapter, snapshot mapping, read-only CLI first contact.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027G](EPIC-027G_spot_testnet_venue_and_credentials.md), [EPIC-027J](EPIC-027J_fake_exchange_spot_routes.md). ADR O6 must be answered before the entry-price criterion.

---

## 1. Context and problem
- `FuturesAccountReader` calls `futures_account`, `futures_get_position_mode` and similar
  endpoints, and reads the `USDT` asset only (`adapters/binance/futures_account_reader.py:58,67,126-152`).
- `LivePosition` is a signed amount with mark price, leverage, margin type and liquidation price
  (`contracts/live_position.py:192-212`).
- The Spot API returns per-asset `free`/`locked` balances (`GET /api/v3/account`). It returns no
  position, no entry price, no mark price and no liquidation price.
- `IAccountSnapshot` already states that Spot would answer `None` for the futures-only fields
  (`i_account_snapshot.py:21-25`). The seam was anticipated, but never filled.
- `ExchangeConnectionStatus` flags hedge mode as unsupported (`exchange_connection_status.py:290`).
  Spot has no such mode.

## 2. Acceptance criteria
- [x] A `SpotHolding` value type carries asset, free, locked and a dust threshold. It has no field that
      Spot does not provide. (`spot_holding.py`; `test_spot_holding.py`)
- [x] A `SpotAccountReader` implements `ITradingAccountReader` over `ping`, `get_server_time` and
      `get_account`, and reports connection, permissions and balances. (`spot_account_reader.py`;
      `test_spot_account_reader.py`)
- [x] `exchange-status` against Spot Testnet (read-only) prints balances, and names a Futures key used
      by mistake as a key error, not a network error. (`exchange_status_formatter.py`'s Spot branch and
      venue-specific `KEY_EXPIRED`/`NOT_CONFIGURED` guidance; `-2015` is the same Binance-API-wide code
      `FuturesAccountReader` already classifies, reused here — `test_exchange_status_formatter.py`)
- [x] Equity for Spot is the quote balance plus holdings × last price. The price source is named in the
      log. (`SpotAccountReader._compute_equity` logs each symbol priced at INFO, and a WARNING plus
      `equity=None` — never a partial sum — the moment one holding cannot be priced;
      `test_equity_is_quote_balance_plus_holdings_priced_at_the_ticker`,
      `test_equity_is_none_not_a_partial_sum_when_a_holding_cannot_be_priced`)
- [x] The average entry price comes from the source chosen in ADR O6. Until then it is shown as
      "not available", never guessed. (This reader has no entry-price field at all rather than a
      fabricated `None` — `GET /api/v3/myTrades` is deferred to a later phase, per O6's own note that it
      belongs to "`EPIC-027H`/Phase 3"; only the account-read shape this task's own file table scopes is
      built now)

## 3. Design
- Holdings are their own type, not a `LivePosition` with zeros (ADR D7; `domain-truth-rule.md`).
  Consumers that need "is something open on this symbol" get a small read port that both markets
  can answer: Futures from its position, Spot from its base balance above dust.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/spot_holding.py` | new value type |
| `src/modules/trading/adapters/binance/spot/spot_account_reader.py` | new adapter |
| `src/modules/trading/contracts/i_account_snapshot.py` and implementers | Spot answers |
| `src/presentation/cli/exchange_status_formatter.py` | Spot output and key-mixup message |

## 5. Testing
- Unit: `test_spot_holding.py` (dust boundary, `total`); `test_spot_account_reader.py` (error
  classification mirroring `test_futures_account_reader.py`'s own table, holdings/dust parsing, equity
  success/failure paths); `test_exchange_status_formatter.py` (Spot rendering, venue-specific guidance);
  `test_module_account_reader_binding.py` (real `StdLibContainer`, both venue directions, mirroring
  `test_module_trading_client_binding.py`'s own doctrine).
- Integration: `test_session_factories_against_fake_server.py::test_create_account_client_syncs_timestamp_offset_against_the_exchange_clock`
  proves `SpotSessionFactory`'s clock-skew correction against the real fake exchange server
  (`EPIC-027J`), the same pattern already proven for `FuturesSessionFactory`.
- Opt-in testnet tier: `EPIC-027P`.
- Ran: `.venv/bin/ruff check`/`format --check` (clean); `mypy` diffed byte-for-byte against a
  clean-cache baseline run on the pre-change tree (untracked files included via `git stash -u`) —
  identical 584 pre-existing errors, zero new; `tests/unit/architecture` 451 passed (after extending
  `test_only_the_session_factory_constructs_binance_client.py`'s allow-list for the new
  `SpotSessionFactory` — a real third construction site, not a loophole);
  `tests/unit/modules/trading` 798 passed; `tests/sanity` 32 passed;
  `tests/integration/infrastructure/binance` 13 passed — 1327 passed total across the targeted suites.
  Full `tests/unit` not completed by the author before this PR (`ci-rule.md`/`commit-rule.md`: the
  author's own gate is the fast tier plus targeted tests; GitHub Actions' `-Full` run is the full-gate
  authority, not a local duplicate — user decision 2026-09-18).

## Implementation notes (written when done)
- Two ports genuinely new beyond the task's own file table, both a direct necessary consequence of
  giving `SpotAccountReader` a signed session to read through: `ISpotSessionFactory`/`ISpotSessionClient`
  (`support/binance_gateway/contracts/`) — a parallel, narrow port to `ITradingSessionFactory`, not a
  widening of it, since `ITradingSessionFactory`'s own docstring already states "this port does not
  parameterize venue because there is never a second one to choose between," an assumption `SPOT_TESTNET`
  broke — and `SpotSessionFactory` (`adapters/binance/spot/`), mirroring `FuturesSessionFactory`'s own
  `BUG-111` clock-skew correction with Spot's unprefixed `get_server_time()` in place of `futures_time()`.
- `ExchangeConnectionStatus` gained two new optional fields, `holdings: tuple[SpotHolding, ...] | None`
  and `equity: Decimal | None`, both defaulted to `None` — the exact symmetric case
  `i_account_snapshot.py`'s own "@par The seam" docstring already named for `position_mode`/`margin_type`
  answering `None` for Spot, now extended in the other direction for Spot-only fields a Futures venue
  answers `None` for. No existing call site needed updating (`pitfalls/source.md` #1: a frozen dataclass
  field needs a default, or every call site breaks).
- Equity is deliberately all-or-nothing: if any non-dust holding's ticker price cannot be fetched,
  `_compute_equity` returns `None` for the whole calculation rather than a partial sum that would
  silently under-report — the same "never guess" discipline the task's own acceptance criteria demand of
  the average entry price, applied consistently to equity too, since a partially-summed number a caller
  cannot distinguish from a complete one is arguably worse than an absent one.
- `test_only_the_session_factory_constructs_binance_client.py`'s allow-list needed extending for the new
  `SpotSessionFactory` — the architecture guard correctly failed on the first run, proving it actually
  scans rather than merely documents the rule (`architecture-rule.md` §7.3).
- `spot_account_reader.py`'s dust threshold (`Decimal("0.00000001")`) and the equity computation's "all
  Spot pairs are `{asset}USDT`" assumption both follow directly from ADR D9 (USDT-quoted pairs only,
  Phase 1) — neither needed a new decision.

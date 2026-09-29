# EPIC-028D — Each desk knows its available balance, wallet, margin and unrealized PnL (Futures) or free/locked and equity (Spot)

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — Futures `walletBalance` is shown today as if it were spendable
**Complexity:** M — a new port, two adapters, a query and a refresh
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028B](../completed/EPIC-028B_venue_addressed_commands.md)

---

## 1. Context and problem
- `ExchangeConnectionStatus.usdt_balance` is Futures `walletBalance` (not `availableBalance`) and
  appears only in the CLI and Settings (`presentation/cli/exchange_status_formatter.py`).
- Spot equity exists (`SpotAccountReader._compute_equity`) but no screen shows it.

## 2. Acceptance criteria
- [ ] `GetAccountSummaryQuery(venue)` returns an `AccountSummary`: Futures → available, wallet, margin balance, unrealized PnL, position mode; Spot → quote free/locked, equity (or `None` per EPIC-027H's never-guess rule).
- [ ] The summary refreshes on the existing poll cadence and on every `OrderFilledEvent` of its venue.
- [ ] `exchange-status` prints available balance for Futures.

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
- Not run.

## Implementation notes (written when done)
Not started.

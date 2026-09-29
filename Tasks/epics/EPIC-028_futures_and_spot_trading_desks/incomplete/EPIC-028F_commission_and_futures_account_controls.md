# EPIC-028F — The Futures desk can change leverage and margin mode, and both desks know their commission rates

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — a leverage change on an open position is refused by Binance; the app must refuse first
**Complexity:** M — two commands, one reader
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028B](EPIC-028B_venue_addressed_commands.md)

---

## 1. Context and problem
- `ITradingClient` has no `change_leverage` / `change_margin_type` (the manual order card's docstring
  says so); leverage today is only a strategy-sizing number.
- No commission rate is read anywhere; fees are only known after a fill (`OrderFilledEvent.fee_amount`).

## 2. Acceptance criteria
- [ ] `ChangeLeverageCommand(venue=FUTURES_TESTNET, symbol, leverage)` and `ChangeMarginTypeCommand(…, CROSSED|ISOLATED)` call the exchange and report its answer; both refuse with a named reason while a position is open on that symbol.
- [ ] Either command on the Spot venue is refused before any network call.
- [ ] `GetCommissionRateQuery(venue, symbol)` returns maker/taker rates (Futures `commissionRate`, Spot `account.commissionRates`).

## 3. Design
A narrow `IFuturesAccountControl` port (not new methods on `ITradingClient`, which Spot also implements — Interface Segregation).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_futures_account_control.py`, `i_commission_rate_reader.py` | new |
| `src/modules/trading/application/commands/change_leverage|change_margin_type/` | new |
| adapters | Futures control, two commission readers |

## 5. Testing
Unit (refusals, happy path); fake-exchange integration for leverage/margin endpoints.
- Not run.

## Implementation notes (written when done)
Not started.

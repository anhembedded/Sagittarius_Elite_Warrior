# EPIC-028F — The Futures desk can change leverage and margin mode, and both desks know their commission rates

**Status:** 🟡 Implemented — awaiting review
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — a leverage change on an open position is refused by Binance; the app must refuse first
**Complexity:** M — two commands, one query, one control port and one reader port (see Implementation notes)
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028B](../completed/EPIC-028B_venue_addressed_commands.md)

---

## 1. Context and problem
- `ITradingClient` has no `change_leverage` / `change_margin_type` (the manual order card's docstring
  says so); leverage today is only a strategy-sizing number.
- No commission rate is read anywhere; fees are only known after a fill (`OrderFilledEvent.fee_amount`).

## 2. Acceptance criteria
- [x] `ChangeLeverageCommand(venue=FUTURES_TESTNET, symbol, leverage)` and `ChangeMarginTypeCommand(…, CROSSED|ISOLATED)` call the exchange and report its answer; both refuse with a named reason while a position is open on that symbol.
- [x] Either command on the Spot venue is refused before any network call.
- [x] `GetCommissionRateQuery(venue, symbol)` returns maker/taker rates (Futures `commissionRate`, Spot `account.commissionRates`).

## 3. Design (as built)
- **Two narrow ports.** `IFuturesAccountControl` changes leverage and margin mode; `ICommissionRateReader` reads the rates. Neither adds methods to `ITradingClient`, which Spot also implements (Interface Segregation).
- **Two new `VenueContext` fields, filled by `VenueAssembly`.**
  - `commission_reader`: Futures or Spot.
  - `account_control`: `FuturesAccountControl`, or `None` on Spot. Absence is the type, so a handler refuses Spot by reading `None`, never by comparing venues.
- **One gate for both commands** (`application/account_control/account_control_gate.py`), checked in this order:
  1. the venue submits nothing (`TRADING_VENUE_DISABLED`);
  2. no control, i.e. Spot (`NOT_A_FUTURES_VENUE`);
  3. the trading switch is off;
  4. the connection is not ready;
  5. an open position on the symbol (`POSITION_OPEN`, with the position in `detail`).

  The first three need no network.
- **The answer.** `AccountControlResult[T]` holds either a refusal or what the exchange confirmed, never both:
  - `LeverageSetting(symbol, leverage, max_notional)`;
  - or the `MarginType` now in effect.

  An exchange refusal comes back as `EXCHANGE_REJECTED` with Binance's code and message. An exchange that never answered raises `AccountControlUnavailableError`, because nothing is known to have changed.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `contracts/i_futures_account_control.py`, `i_commission_rate_reader.py` | new ports |
| `contracts/commission_rate.py`, `leverage_setting.py`, `account_control_result.py`, three error types | new value and error types |
| `contracts/venue_context.py` | `commission_reader`, `account_control` fields |
| `adapters/binance/futures_account_control.py`, `futures_commission_rate_reader.py`, `spot/spot_commission_rate_reader.py` | new adapters |
| `application/account_control/change_leverage/`, `change_margin_type/`, `account_control_gate.py` | new commands and their shared gate |
| `application/queries/get_commission_rate/` | new query |
| `composition/venue_assembly.py`, `command_bindings.py`, `query_bindings.py` | wiring |
| `support/binance_gateway/contracts/i_trading_session_factory.py` | the three SDK calls on the session protocol |
| `tests/sanity/fake_exchange/` | `leverage`, `marginType`, `commissionRate` routes; Spot `commissionRates` |

## 5. Testing
- **Unit, handlers** (`test_account_control_commands.py`). These run over the real Futures adapters; only the raw SDK session is a `Mock`. They cover:
  - the happy path for both commands;
  - `-4046` read as "already in effect";
  - an exchange refusal carrying its code;
  - an open position refused before the change is sent;
  - Spot, `DISABLED` and the switch off, each refused with no session opened and no connection check;
  - both halves of the connection check;
  - a transport failure raising with its cause chained;
  - the leverage range 1 to 125 at both ends;
  - the result invariant.
- **Unit, readers** (`test_commission_rate_readers.py`): each venue's payload; a negative maker rate kept as a rebate; failures translated with their cause; no credentials means no request.
- **Unit, query** (`test_get_commission_rate.py`): each venue answers with its own rates. The assembly test checks the new adapter types and that Spot's control is `None`.
- **Integration** (`test_account_controls_against_fake_server.py`), over HTTP to the fake exchange:
  - a leverage change and its confirmation;
  - `-4028` for 200x;
  - changing to isolated twice;
  - both commission readers.
- **Mutation check:** 15 targeted mutations, all killed. The first pass left one survivor, the `reachable` half of the connection check; a case for "unreachable with no failure" now covers it.

## Implementation notes
- **No current-setting read.** `positionRisk` v3 no longer carries leverage or margin mode (`BUG-114`). Reading them needs `GET /fapi/v1/symbolConfig`, which is named in the port docstring as the next method. A desk that shows the current setting (`EPIC-028I`) adds it.
- **Spot rates are account-wide.** The per-symbol `/api/v3/account/commission` endpoint is not wrapped by the pinned `python-binance`. A symbol-specific Spot discount is therefore not seen, and the port docstring says so.
- **The trading switch gates both commands.** Changing leverage is signed account activity, gated like a cancel. With the switch off nothing is sent.
- **Margin mode with open orders.** Binance refuses that change (`-4047`). It is not pre-checked; the refusal comes back as `EXCHANGE_REJECTED` with the exchange's message.
- **Not verified live.** Payload shapes and error codes follow Binance's documented API. Egress to Binance is blocked here, the same disclosure the other adapters make.

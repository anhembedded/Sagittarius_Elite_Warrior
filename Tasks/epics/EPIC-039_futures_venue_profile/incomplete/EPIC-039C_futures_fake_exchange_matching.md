# EPIC-039C — The fake Futures exchange matches resting orders, so a Futures ladder can be tested end to end

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10; [DESIGN §1.4](../DESIGN_2026-10-10_futures_venue_profile.md).
**Risk:** 🟡 — test infrastructure; a fake kinder than Binance gives false confidence
**Complexity:** L — a matcher, position and wallet movement, funding, liquidation, user-stream events
**Epic:** [EPIC-039](../README.md)
**SPEC:** none (test infrastructure).
**Design:** [DESIGN §1.4, §13](../DESIGN_2026-10-10_futures_venue_profile.md) · **Research:** [§8](../RESEARCH_2026-10-10_futures_grid.md)
**Depends on:** None (can start in parallel with 039A).

---

## 1. Context and problem
`tests/sanity/fake_exchange/order_book_state.py` says of Futures: "Still not a matching engine: a resting order never fills." A MARKET order fills at once against a fixed book and moves the position and wallet; a reduce-only order that would not reduce is refused with `-2022`; conditional orders live in `futures_algo_orders.py` and trigger on `move_price`. Spot has a matcher (`spot_order_book.py`: `rest`, `take`, `trade_at`). A Futures Grid is a ladder of resting LIMIT orders, so without a matcher its executor can only be tested by mocks — the shape that let `BUG-013` "pass" twice (`fix-bug-rule.md` §4).

### Facts verified on `master-warrior` `076d339`
- Files: `tests/sanity/fake_exchange/{server.py (275), futures_routes.py (308), order_book_state.py (180), futures_account_state.py (212), futures_algo_orders.py (187), futures_market.py (109), futures_symbol_config.py (75), spot_order_book.py (96), history_log.py (160)}`. `tests/sanity/binance_fake_server.py` is a stable shim: **its name and signature must not change** (many callers import it flat after `sys.path.insert`).
- Futures routes present: ping, time, account, `positionRisk` v3 (no `leverage`/`marginType` field, `BUG-114`), leverage, margin type, leverageBracket, premiumIndex, bookTicker, orders, algo orders, userTrades, allOrders. Brackets are a fixed `BTCUSDT`-shaped table (`futures_market.py`).
- The bots integration world (`tests/integration/modules/bots/conftest.py`, `grid_fake_exchange.py`) patches only `Client.API_TESTNET_URL` to the **Spot** URL and sets `SPOT_ENV_API_KEY/SECRET`; Futures needs the `BINANCE_FUTURES_*` env pair and the futures URL patch (`binance_client_builder.py` decides how the client is built — read it).
- The fake has no websocket (`grid_fake_exchange.py` docstring: "the fake's missing websocket"): fills reach the bot in Spot tests through the order response (`BOT-173`) and `GET` reads, not a stream. A Futures test world must do the same or add a stream — decide and record.

## 2. Acceptance criteria
- [ ] A resting Futures LIMIT order **fills when the fake's mark/last price crosses it** (BUY when price ≤ limit, SELL when price ≥ limit), partially if the test asks, updating position (signed), average entry, wallet balance, margin and the `positionRisk`/`account`/`userTrades`/`allOrders` the routes report. `move_price(symbol, price)` (existing for algo orders) drives it.
- [ ] One-way semantics: a fill that reduces a position realises PnL; one that crosses zero flips it; a **reduce-only** order that would increase is refused `-2022` (exists) and one larger than the position is capped (exists) — both still hold with resting orders (a resting reduce-only order is cancelled by the fake when the position can no longer be reduced: **to verify** Binance's behaviour first and record the page; implement what the page says).
- [ ] **Funding:** a test can set a funding rate and advance the fake's clock across a funding time; the position is charged/credited accordingly in the wallet and a user-stream `ACCOUNT_UPDATE` (if a stream exists) or the account read shows it. Field names **to verify** against the official docs (RESEARCH §8).
- [ ] **Liquidation:** when the mark price crosses the position's liquidation price (the fake computes it with the same formula as `trading/contracts/liquidation_estimate.py`, isolated margin), the fake closes the position, zeroes its margin, cancels the symbol's orders and records the forced fill so the bot can see "a fill I did not order". Identification of a forced close **to verify** (RESEARCH §8).
- [ ] The fake can be asked for **faults** in the spirit of `EPIC-037E` (a rejected order, a delayed fill, a duplicated report) without changing the default behaviour of existing Spot tests.
- [ ] A `futures` pytest fixture (beside the existing `exchange` fixture, same module) builds the composed app over the Futures venue with the right env keys and URL patches; the existing Spot `exchange` fixture and every Spot test are untouched and green.
- [ ] Unit tests of the matcher itself (price cross, partial fill, reduce-only, flip, funding, liquidation) in `tests/sanity/` or beside the fake, each shown red before the matcher.

## 3. Design
Mirror `spot_order_book.py` (same `rest/take/trade_at` verbs) so the two fakes read alike; keep the Futures-only parts (position, funding, liquidation) in `futures_account_state.py`; no file past 400 lines (`architecture-rule.md` §5.4) — split `futures_matching.py` and `futures_funding.py`. Demand over comfort: the fake must be able to be *unfair* (late, duplicated, rejected) because the bugs this app has had were about exactly that.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/sanity/fake_exchange/futures_matching.py` (new) | resting-order matching on `move_price` |
| `tests/sanity/fake_exchange/order_book_state.py` | rest LIMIT orders; call the matcher; docstring updated ("a resting order fills on a cross") |
| `tests/sanity/fake_exchange/futures_account_state.py` | signed position, entry, realised PnL, margin |
| `tests/sanity/fake_exchange/futures_funding.py` (new), `futures_market.py` | funding rate and clock |
| `tests/sanity/fake_exchange/futures_liquidation.py` (new) | the forced close |
| `tests/integration/modules/bots/conftest.py`, `grid_fake_exchange.py` | the `futures` fixture; faults API |
| `tests/sanity/test_fake_futures_matching.py` (new) | the matcher's own tests |

## 5. Testing
Tier: sanity/unit for the fake itself; its first consumer is `039D`.
- `test_a_resting_buy_fills_when_price_falls_to_it` · `test_a_resting_sell_fills_when_price_rises_to_it` · `test_a_partial_fill_leaves_the_rest_resting`
- `test_a_fill_that_crosses_zero_flips_the_position_and_realises_pnl`
- `test_funding_is_charged_to_the_side_the_rate_favours_against`
- `test_a_mark_price_through_the_liquidation_price_closes_the_position_and_cancels_orders`
- `test_the_spot_fixture_and_spot_journeys_are_unchanged`
Not run yet.

## Pitfalls
- `binance_fake_server.py` is a flat-import shim; do not rename, move or change its exports.
- `positionRisk` v3 has no `leverage`/`marginType` (`BUG-114`): the fake mirrors the real shape, so leverage comes from `symbolConfig`; do not "helpfully" add the fields.
- Do not make the fake fill a resting order at a price *better* than the limit unless Binance does (it fills at the limit or better for a crossing book; keep the rule explicit and tested).
- The Futures venue's env var names are `BINANCE_FUTURES_TESTNET_API_KEY/SECRET` (`env_first_credentials_provider.py`); the Spot fixture sets the Spot pair.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: read `binance_client_builder.py` and `grid_fake_exchange.py` to decide how Futures fills reach the bot (response, `GET`, or a fake stream) and record the decision here.

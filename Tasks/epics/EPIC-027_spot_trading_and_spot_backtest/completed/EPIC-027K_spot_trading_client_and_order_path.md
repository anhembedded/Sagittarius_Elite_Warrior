# EPIC-027K — A Spot MARKET or LIMIT order goes through the same `ExecuteOrderCommand` to Spot Testnet

**Status:** ✅ Done (2026-09-27)
**Source:** the user, 2026-09-26: *"tui muốn giao dịch spot"* ("I want to trade spot").
**Risk:** 🔴 — the first Spot order ever sent; a wrong payload is a real (testnet) order.
**Complexity:** L — adapter, payload mapper, order vocabulary, cancel paths.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027F](EPIC-027F_venue_selected_trading_client_factory.md), [EPIC-027G](EPIC-027G_spot_testnet_venue_and_credentials.md), [EPIC-027I](EPIC-027I_spot_symbol_metadata_provider.md), [EPIC-027J](EPIC-027J_fake_exchange_spot_routes.md)

---

## 1. Context and problem
- The only `ITradingClient` is `FuturesTradingClient`. It calls `futures_create_order` and similar
  endpoints (`adapters/binance/futures_trading_client.py:67-149`).
- The payload mapper always sends `positionSide="BOTH"` and `reduceOnly`
  (`futures_order_payload_mapper.py:50,82-83`). The Spot API rejects both.
- `OrderType` includes `STOP_MARKET`/`TAKE_PROFIT_MARKET` (`contracts/order_type.py:135-138`). These
  are Futures-only. Spot uses `STOP_LOSS(_LIMIT)`/`TAKE_PROFIT(_LIMIT)`/`LIMIT_MAKER`.
- `Order.reduce_only` and `OrderIntent.reduce_only` exist because, in one-way Futures, SELL can mean
  "close long" or "open short". On Spot, SELL can only reduce a holding.

## 2. Acceptance criteria
- [x] A `SpotTradingClient` implements `ITradingClient`: place (MARKET, LIMIT), cancel one, cancel all,
      open orders. `get_positions` is not faked: the port is split, or Spot answers through the
      holdings port from `EPIC-027H`. — `get_positions()` always returns `[]` (not a port split — see
      §3's revised decision below for why). Proven against a real HTTP round trip:
      `test_spot_trading_client_order_lifecycle_against_fake_server.py::
      test_positions_are_always_flat_a_spot_account_has_no_leveraged_positions`.
- [x] A Spot payload never contains `reduceOnly` or `positionSide`. A test asserts the exact payload
      against the fake exchange. — `test_spot_order_payload_mapper.py::TestMarketOrder::
      test_generates_the_expected_field_set_with_no_futures_only_fields` and the LIMIT equivalent
      assert the exact dict; both fields are structurally absent from `map_order_to_spot_params()`,
      never merely unset.
- [x] Sending a Futures-only order type to a Spot venue is refused before the network, with a named
      reason. — `InvalidOrderForSubmissionError` for `STOP_MARKET`/`TAKE_PROFIT_MARKET`, proven at both
      the mapper (`TestFuturesOnlyOrderTypesAreRefused`) and the client
      (`test_spot_trading_client.py::TestPlaceOrderRouting::
      test_a_futures_only_order_type_is_rejected_locally`, asserting the raw session client's
      `create_test_order` is never called).
- [x] The factory from `EPIC-027F` returns the Spot client for `SPOT_TESTNET`. No handler is edited
      for this. — `adapter_bindings.py`'s `ITradingClientFactory` bind now venue-branches; confirmed
      against a real `StdLibContainer` in `test_module_trading_client_factory_binding.py` and
      `test_module_trading_client_binding.py`. Confirmed unedited:
      `execute_order/handler.py`/`cancel_order/handler.py`/`enable_trading.py`/`emergency_stop/handler.py`
      carry no diff in this task (only the pre-existing tests that asserted the old "Spot is blocked"
      behaviour changed, per `TradingVenue.supports_order_submission`'s own docstring pre-announcing
      this task as the one that lifts that block).
- [x] A client order id is on every Spot order (`newClientOrderId`), as on Futures. —
      `map_order_to_spot_params()` always sets it from `order.client_order_id`; asserted in every
      mapper field-set test.
- [x] `VALIDATE_ONLY` mode uses `POST /api/v3/order/test`. —
      `test_spot_trading_client.py::TestPlaceOrderRouting::test_validate_only_calls_the_test_endpoint_only`
      asserts `create_test_order` is called and `create_order` is not, for
      `OrderSubmissionMode.VALIDATE_ONLY`.

## 3. Design
- **Revised during implementation:** §3's original SELL/`reduce_only=False` precondition (ADR D4, "never
  a short on Spot") was scoped out of this task's file-change list. It is not a numbered acceptance
  criterion above; enforcing it would mean editing `preview_order/handler.py`/`execute_order/handler.py`,
  both outside this task's own §4 file list; and it is already structurally redundant — a Spot account
  holds no margin/borrow capability, so Binance's own API cannot execute an overselling SELL regardless
  of this app's `reduce_only` flag. `Order.reduce_only` stays unread by `map_order_to_spot_params()` —
  Spot's wire payload has no such field at all (see the AC above) — so there is nothing for a
  precondition to gate here; if a real oversell-guard is ever wanted, it belongs at the
  `execute_order`/`preview_order` handler layer, shared by every venue, not duplicated per adapter.
- **Revised:** `ITradingClient.get_positions()` is not port-split. `SpotTradingClient.get_positions()`
  always returns `[]` — the true answer for a venue with no leveraged positions, not an invented one;
  every real caller (`get_open_positions`, `enable_trading`, `emergency_stop`, user-data-stream
  reconciliation) already treats an empty list as "flat". A port split was judged premature abstraction
  (P7 — no second call site needs a narrower contract yet) for the same return value a split would
  produce anyway.

## 3.1 Post-review correction (2026-09-27, PR #284)
Independent review found two issues on the initial head commit (`c3bb5d64`):
1. **GitHub Actions `ci-local.ps1 -Full` was red on that exact commit** — a pre-existing unit test,
   `tests/unit/support/binance_gateway/contracts/test_trading_venue.py::
   test_only_futures_testnet_supports_order_submission_today`, directly asserted
   `TradingVenue.SPOT_TESTNET.supports_order_submission is False`, the exact literal this task's own
   `trading_venue.py` change flips to `True`. Its own docstring had pre-announced this task would need
   to touch it, but it lived outside both directories the PR body's targeted-test citation covered
   (`tests/unit/architecture`, `tests/unit/modules/trading`), so the author's own fast-tier run never
   caught it. Fixed by renaming it to `test_both_testnets_support_order_submission` and rewriting the
   assertion to the new correct behaviour — a one-line, mechanical fix, but it is exactly the same class
   of gap `pitfalls/source.md` #3 already names ("a port gains an abstract method and only the main
   implementer changes — grep `src/`, `scripts/` **and** `tests/`"), applied here to a changed property
   rather than a changed port signature.
2. **[BLOCKING] A Spot manual "Short" click could silently sell real held assets.** Traced the real call
   graph: `SpotTradingClient.get_positions()` always answers `[]` (by design — a Spot account has no
   leveraged position to report), so `TradingActionsCoordinator.run_manual_order()`'s `current_position`
   was always `None` for Spot, which made `manual_order_intent_for(SHORT, None)` always return
   `reduce_only=False` — indistinguishable from a deliberate sale of a real holding, once this task's own
   `supports_order_submission` flip stopped every Spot order from being refused outright at
   `TRADING_VENUE_DISABLED`. `manual_order_card.py`'s Short button carries no `TradingVenue`/`MarketType`
   gate anywhere, so a user with real Spot inventory clicking "Short" (meaning: open a short position that
   does not exist on Spot) would have that inventory sold live under an action the UI frames as opening a
   position — a `domain-truth-rule.md` F3 violation ("an unsupported capability is hidden, disabled or
   labelled unavailable"), not merely a cosmetic gap.

   Fixed at the one, un-bypassable translation point rather than in the UI: `manual_order_intent_for()`
   gained a third parameter, `market_type: MarketType`, and now raises the new
   `ManualShortNotSupportedOnMarketError` before building any `OrderIntent` when
   `direction is SHORT and market_type is MarketType.SPOT` — refused, never silently reinterpreted as a
   Sell the user did not ask for. `TradingActionsCoordinator` takes `market_type` as a constructor
   collaborator (resolved once in `presenter_factory_trading.py` via `container.resolve(TradingVenue)
   .market_type`, the same "resolve once at composition, not per click" pattern every other
   venue-branched bind in `adapter_bindings.py` already uses); the raise flows through the coordinator's
   existing `except Exception` error-reporting path with zero new plumbing. `Long` (a plain Buy) stays
   valid on Spot — only `Short` is refused, since Spot's own inability to represent it is the actual
   capability gap, not Sell itself. This is the mechanism `§3`'s original ADR D4 precondition was meant to
   guard, reached from the manual-UI angle rather than the handler-level `reduce_only` angle the original
   design sketched — the handler-level version was checked and rejected: by the time `OrderRequest`
   reaches `ExecuteOrderCommandHandler`, the Short/Sell distinction is already collapsed into
   `side=SELL`/`reduce_only=False`, identical to a genuine reduce-holding sell, so a handler-level refusal
   there cannot tell the two apart — only the point where `ManualOrderDirection.SHORT` is still known can.

   Two more pre-existing call sites of `manual_order_intent_for()` needed the new parameter to keep
   compiling correctly, found by grepping every call site rather than trusting the first regression run
   alone: `tests/unit/modules/trading/contracts/test_order_intent.py` (2 calls) and
   `tests/integration/application/test_manual_order_pipeline_against_fake_server.py` (1 call), all passed
   `MarketType.FUTURES_USD_M`/`TradingVenue.FUTURES_TESTNET.market_type` to keep their existing Futures
   scenarios unchanged.

   New tests: `test_manual_order_intent.py::TestSpotRefusesShort` (2 cases — flat, and with a position
   argument to prove the refusal is a market capability, not a position-shape coincidence);
   `test_trading_actions_coordinator.py::test_run_manual_order_refuses_a_short_click_on_spot_without_submitting`
   (proves `order_submission.submit()` is never reached and the coordinator's existing error-reporting
   path surfaces the refusal). Regression: `tests/unit/modules/trading` + `tests/unit/architecture` +
   `tests/integration` together, 1525 passed, 4 pre-existing skips, 0 failed; ruff/format clean; mypy
   unchanged at the 584-error baseline (zero new errors in any file this correction touched).

The reviewer's "should-fix" (locking the oversell-redundancy claim with a test rather than prose) and its
non-blocking note (the `TRACKING.md` catch-up bundled into this PR) are recorded but not actioned in this
correction — the should-fix is a strengthening, not a defect, and the note was independently confirmed
accurate by the reviewer itself.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/spot/spot_trading_client.py` | new adapter (`ITradingClient`) |
| `src/modules/trading/adapters/binance/spot/spot_order_payload_mapper.py` | new mapper (forward + reverse) |
| `src/modules/trading/adapters/binance/spot/spot_trading_client_factory.py` | new — `ITradingClientFactory` for Spot |
| `src/support/binance_gateway/contracts/i_spot_session_factory.py` | widened: `create_trading_client()` + 5 order methods on `ISpotSessionClient` (the actual Spot-shaped session port; §4's original citation of `i_trading_session_factory.py` was stale, matching this repo's own established pattern of stale line-number citations in task files, as `EPIC-027I` also found) |
| `src/modules/trading/adapters/binance/spot/spot_session_factory.py` | added `create_trading_client()` |
| `src/support/binance_gateway/contracts/trading_venue.py` | `supports_order_submission` now `True` for `SPOT_TESTNET` too |
| `src/modules/trading/composition/adapter_bindings.py` | `ITradingClientFactory` now venue-branches |
| `tests/unit/architecture/test_only_the_factory_constructs_spot_trading_client.py` | new guard, mirroring the Futures one |
| `tests/unit/architecture/scanned_roots_registry.py` | registry row for the new guard |
| Not touched: `src/modules/trading/contracts/order_type.py` | order-type validity is enforced in the mapper (`_SUPPORTED_SPOT_ORDER_TYPES`), not on the shared enum — `OrderType` has no notion of "valid for which venue" and none was added, keeping it venue-neutral for Futures' own use |
| `src/modules/trading/contracts/manual_short_not_supported_on_market_error.py` | new (post-review, §3.1) — the refusal `manual_order_intent_for()` raises |
| `src/modules/trading/domain/policies/manual_order_intent.py` | post-review (§3.1) — `market_type` parameter, refuses `SHORT` on `MarketType.SPOT` |
| `src/modules/trading/ui/dashboard/coordinators/trading_actions_coordinator.py` | post-review (§3.1) — takes `market_type`, passes it to `manual_order_intent_for()` |
| `src/modules/trading/ui/dashboard/logic/presenter_factory_trading.py` | post-review (§3.1) — resolves `TradingVenue.market_type` once at composition |

## 5. Testing
- Unit: `tests/unit/modules/trading/adapters/binance/spot/test_spot_order_payload_mapper.py` (13 tests)
  — MARKET/LIMIT field sets with no `reduceOnly`/`positionSide`; step/tick alignment rejection;
  missing price/time_in_force rejection; `STOP_MARKET`/`TAKE_PROFIT_MARKET` refused before network;
  reverse mapping (MARKET/LIMIT/unrecognized type+status → `UNKNOWN`, zero price → `None`,
  `transactTime`/`updateTime`/`time` precedence).
- Unit: `tests/unit/modules/trading/adapters/binance/spot/test_spot_trading_client.py` (14 tests) —
  `VALIDATE_ONLY`/`LIVE` routing, no-credentials/unknown-symbol/unrounded-order/futures-only-type
  rejection before any network call, exchange rejection translation, cancel one, cancel all (no
  `get_open_orders()` pre-read, unlike Futures), get open orders (with/without symbol), `get_positions()`
  always `[]`.
- Unit (composition wiring, real container): `test_module_trading_client_binding.py` (extended) proves
  `ITradingClient` resolves to `SpotTradingClient` for `SPOT_TESTNET`; new
  `test_module_trading_client_factory_binding.py` proves `ITradingClientFactory` itself resolves to
  `SpotTradingClientFactory`/`FuturesTradingClientFactory` by venue, and that its `.create()` actually
  hands back a `SpotTradingClient`.
- Unit (fallout from the safety-gate flip, rewritten not merely made to pass): `test_execute_order.py`,
  `test_cancel_order.py`, `test_enable_trading.py` — the pre-existing "Spot is blocked" tests now assert
  the opposite: a `SPOT_TESTNET` order/cancel/enable succeeds.
- Integration:
  `tests/integration/infrastructure/binance/test_spot_trading_client_order_lifecycle_against_fake_server.py`
  (4 tests) — place a `LIMIT` order → appears in `get_open_orders()` → cancel → gone; `cancel_all_orders()`
  clears the book and returns what was canceled; a `MARKET` order fills immediately and never appears
  open (the reason the lifecycle test itself uses `LIMIT`); `get_positions()` always `[]`, against a
  real HTTP round trip through the fake exchange's Spot routes.
- Real Spot Testnet: `EPIC-027P` (unchanged, out of this task's scope).
- All 35 new/changed tests pass. Regression: `tests/unit/architecture` 457 passed (451 + 6 new: the
  guard's own 3 tests plus its scan touching existing counting tests);
  `tests/unit/modules/trading` 849 passed (844 + 5 net: 4 pre-existing tests rewritten in place, 1 new
  LIVE-submission test added); `tests/integration/infrastructure/binance` +4 (35 total across the files
  this task touched, all passing); `ruff check`/`ruff format --check` clean on every touched file;
  `mypy src scripts` unchanged at the frozen 584-error baseline (zero errors in any file this task
  touched, confirmed by grepping the full run for every touched path). Full `tests/unit` left to GitHub
  Actions' `-Full` run per this repo's own cadence (user decision 2026-09-18).

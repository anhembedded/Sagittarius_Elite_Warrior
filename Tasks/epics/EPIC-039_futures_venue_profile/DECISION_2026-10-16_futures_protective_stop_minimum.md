# ADR — A Futures bot's protective stop is the minimum `EPIC-039L` builds itself, a `closePosition` conditional order the bot owns, saved before it is sent and cancelled only after the position is flat

**Epic:** [EPIC-039](README.md)
**Date:** 2026-10-16
**Status:** Accepted for D1; Proposed for D2–D12 (an agent's design, reviewed in the pull request of C1; the owner may veto any row); O1–O3 open
**Decided by:** D1 the owner, relayed by the coordinating session `session_01PZn6EWxn6gytSGKwbuRJGg` on 2026-10-16: the owner decided "to build the minimum now, as 4 sequential PRs" instead of waiting for `EPIC-026K`. D2–D12: the author session of `EPIC-039L` C1, delegated by the same message ("decide what C2 to C4 change … record any real choice as a decision record"). None of D2–D12 is a default settled under ONBOARDING §7: each touches real-money behaviour, so each waits for review and the owner's veto, and no row carries a Constitution check.
**Supersedes / superseded by (optional):** completes O7, O8 and O12 of [`DECISION_2026-10-10`](DECISION_2026-10-10_futures_venue_profile.md) §4a; does not change them.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the code tree at `master-warrior` `88e283f` (2026-10-16), cited by path and symbol |
| 🌐 Docs read | read on Binance's official page on 2026-10-16, URL in §1 |
| ⚠️ Unverified | Binance's page did not say, or did not render; it is a testnet check (T1–T5, §6) the owner records before the row it blocks is relied on |
| 🟢 User decision | decided by the owner |
| 🤖 Agent decision | delegated to the author session; reviewable, vetoable |
| ❓ Open | needs the owner; blocks the named PR |

## 1. Context

**The problem.** A Futures bot that halts (`price_feed_stale`, stream down, a rejected key, a switch-off) closes its position, or, for the halts that cannot send an order, leaves it bare. The only protection that survives a dead app is an order resting on the exchange. `EPIC-039H` closes on every halt and says so (`bots/application/services/positions/closer_futures.py` → `PositionExposureCloser.closes_on_halt`), so today nothing is left bare by design, and nothing recovers by itself either. `EPIC-039L` makes *leaving* a position acceptable by putting the exit on the exchange.

**What is established in the repository** (✅):
- `EPIC-026K` has no code: its status is Backlog and `OrderType.STOP_MARKET` is the only trace of it. Its design is a *strategy* entry flow (a stop after each entry fill, `quantity`-sized, journaled by `EPIC-026G`, exempt from the strategy limits). There is no "026K mapping" to reuse.
- What *is* there is the Algo Order mapping of `EPIC-028R`/`028I`: `trading/adapters/binance/futures_algo_order_mapper.py` → `map_order_to_futures_algo_params`, `map_futures_algo_payload_to_order`, `trading/adapters/binance/algo_update_parser.py` → `parse_algo_update`, `trading/adapters/binance/algo_order_links.py` → `AlgoOrderLinks`, and `trading/adapters/binance/futures_trading_client.py` → `FuturesTradingClient` (`get_open_orders` lists regular and algo orders together; `cancel_order` falls back to the algo cancel; `cancel_all_orders` cancels both kinds). It sends `quantity` and `reduceOnly`, `workingType=CONTRACT_PRICE` always, and never `closePosition`; `trading/contracts/order.py` → `Order` has no `close_position` field.
- The fake has the endpoint but not the semantics: `tests/sanity/fake_exchange/futures_algo_orders.py` → `FuturesAlgoOrders` stores `quantity`, ignores `closePosition`, triggers by `place_order` with that `quantity`, has no `EXPIRED`.
- A bot's orders carry `SEW-{tag}-{hex10}` (`trading/contracts/client_order_id.py` → `generate_client_order_id`, `tag_of`). `bots/application/kinds/grid/grid_housekeeping.py` → `GridHousekeeping.cancel_tagged` cancels every open order carrying the tag, so a tagged stop would be cancelled by every ordinary stop and halt unless it is excluded.
- `trading/application/session/emergency_stop/handler.py` → `EmergencyStopCommandHandler._stop` cancels every order of every symbol first (including algo orders, through `cancel_all_orders`), then closes the positions. A failed close after the cancels leaves a bare position.
- Futures mainnet is closed by `bots/contracts/venue_profile.py` → `CLOSED_VENUES`, `bot_closed_reason`, called through `bots/application/services/venue/closed_venue.py` → `closed_venue_refusal` by create, change-venue, start, host start, resume and resume-for-host. There is no "offered flag" in the code; the task's mention of one in `039J` is a plan, not a fact.
- The host's shutdown policy is the port `operations/contracts/i_shutdown_policy.py` → `IShutdownPolicy` (`apply(ledger, give_up)`), with `LeaveOrdersResting` and `StopBotsFirst`; the host picks one from `--on-stop` (`operations/cli/run_command.py`).
- The start already refuses a foreign position on the symbol (`OwnerBudgetRefusal.FOREIGN_POSITION`, `bots/application/kinds/grid/grid_housekeeping.py` → `refusal_text`) and a symbol has one owner (`claim_symbol`).

**What the official documentation says** (🌐, read 2026-10-16; base `https://developers.binance.com/docs/derivatives/usds-margined-futures/`):
- `trade/rest-api/New-Algo-Order` — `POST /fapi/v1/algoOrder`, weight 1 on the 10-second and 1-minute *order* limits and 0 on the IP limit. `algoType` is `CONDITIONAL` only. `closePosition` ("Close-All") is used with `STOP_MARKET` or `TAKE_PROFIT_MARKET`; "Cannot be used with `quantity`", "Cannot be used with `reduceOnly`"; when triggered it closes all of the current long position (for SELL) or short position (for BUY); in Hedge Mode a BUY cannot close LONG nor a SELL close SHORT. `workingType` is `MARK_PRICE` or `CONTRACT_PRICE`, default `CONTRACT_PRICE`. `priceProtect` (default false) limits the trigger when mark and contract price diverge beyond the symbol's `triggerProtect` (from `exchangeInfo`). `clientAlgoId` matches `^[\.A-Z\:/a-z0-9_-]{1,36}$` and is "a unique id among open orders". `selfTradePreventionMode` defaults to `NONE` for algo orders.
- `trade/rest-api/Query-Algo-Order` — `GET /fapi/v1/algoOrder`, weight 1, by `algoId` or `clientAlgoId` (one is required); the answer carries `algoStatus`, `actualOrderId` (empty until triggered), `closePosition`, `workingType`, `triggerPrice`. A `CANCELED` or `EXPIRED` order with no fill is no longer found 3 days after creation; none is found after 90 days.
- `Cancel-Algo-Order` (as listed with the Query page) — `DELETE /fapi/v1/algoOrder`, weight 1, by `algoId` or `clientAlgoId`.
- `user-data-streams/Event-Algo-Order-Update` (read through the site's search summary; the page text itself did not render) — the stream's `ALGO_UPDATE` carries `caid`, `aid`, `ai` (the regular order a trigger placed), `X` (status: `NEW`, `CANCELED`, `TRIGGERING`, `TRIGGERED`, `FINISHED`, `REJECTED`, `EXPIRED`), `wt` (working type), `cp` (close-all), `R`, `rm` (failure reason). `EXPIRED` is "canceled by the system", the example given being a user who closes all positions on the symbol while a `GTE_GTC` conditional order is open.
- `trade/rest-api/Auto-Cancel-All-Open-Orders` — `POST /fapi/v1/countdownCancelAll`; `countdownTime` in milliseconds, `0` disables; "should be called repeatedly as heartbeats". The page does **not** say whether conditional orders are covered.

**What the documentation did not say** (⚠️; the three pages that matter did not render, or are silent): (1) whether a `closePosition` order is **rejected when there is no position** at placement; (2) whether it **survives a position passing through zero** (the `EXPIRED` example suggests it may not); (3) whether a triggered `closePosition` order **with no position on its side** (a BUY stop while the bot is long) does nothing or opens a position; (4) the *exact* error when the trigger is already on the wrong side of the market ("Order would immediately trigger", `-2021`, is documented for the trailing stop only); (5) the order of `ORDER_TRADE_UPDATE` and `ACCOUNT_UPDATE` for one trade; (6) whether `countdownCancelAll` cancels conditional orders; (7) the current-open-algo-orders page (`Current-All-Algo-Open-Orders`) did not render, so its parameters are taken from the repository's use of it (`futures_get_open_algo_orders`) and not re-read. Each is a testnet check in §6; none is guessed here.

## 2. Decisions

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | `EPIC-039L` builds the minimum itself, as four pull requests in order (C1 design, C2 the stop life cycle, C3 the halt policy, C4 the mainnet gate and the soak checklist). It does not wait for `EPIC-026K`, which has no code; `026K`, when it lands, adopts the bot's stop mapping (D2) and keeps its own entry-fill flow. | Accepted | 🟢 the owner, relayed by the coordinating session, 2026-10-16 | `EPIC-039` no longer depends on `026K` for 039L; the row in `TRACKING.md` closes. 026K's file gets a note that the mapping now exists (C2) |
| D2 | **One mapping, extended; no parallel one.** `Order` gains `close_position: bool = False` and `working_type: WorkingType = LAST_PRICE`; `map_order_to_futures_algo_params` sends `closePosition=true` and **no `quantity` and no `reduceOnly`** when `close_position` is set, and `workingType` from the order. Every existing caller keeps `CONTRACT_PRICE`, `quantity`, `reduceOnly` byte for byte. The parser and the read mapping learn `cp`/`closePosition`/`wt`. | Proposed | 🤖 | Additive in the contract (a defaulted field); the desk's stops are unchanged and a test names that. `quantity` for a close-all order is a request the mapper refuses, so the rejected-order pitfall of the task is closed in one place |
| D3 | The trigger is on **mark price** (`workingType=MARK_PRICE`) and `priceProtect=false`. | Proposed | 🤖 | Liquidation is judged on mark (design 039 §7, R1), so a stop that fires on a last-price wick the mark never reached costs a position for nothing, and one that waits on a last price while mark is already at liquidation is too late. `priceProtect=true` could *withhold* the trigger in a spike, which is the one moment a protective order must fire; the cost is a stop that can fire on a mark/last divergence, accepted for a protective order |
| D4 | **Two kinds, one life cycle:** a *stop loss* (`STOP_MARKET`) and, when the plan has a take profit, a *take profit* (`TAKE_PROFIT_MARKET`), each `closePosition`. A bot's protective orders are told from its ladder by **type and `closePosition`, never by a new id shape**: a ladder never holds a conditional order, so `tag_of(id) == bot tag` **and** `close_position` identifies them, and `client_order_id.py` does not change. The ladder reads (`cancel_tagged`, the reconcile's open-order set, the orphan count) **exclude** them. When one of the two is `TRIGGERED` or `FINISHED`, the other is cancelled in the same step (a closed position's second stop is the orphan the task warns about) | Proposed | 🤖 | No new id pattern means no change to a rule every bot's reconcile depends on (`tag_of`); the cost is one extra predicate in the places that list orders. A bot with no stop-loss price (O3 allows it at leverage 1) has **no stop**, is *unprotected*, and halts by closing |
| D5 | **Persist first, idempotent send.** The stop's `clientAlgoId` is generated and the record `INTENDED` is saved in the bot's runtime **before** the request is sent; `STANDING` is saved on the answer. A crash or a timeout between the two is resolved by `GET algoOrder?clientAlgoId=`: found → `STANDING`; `-2013` (not found) → send again with the same id, which Binance accepts once ("unique among open orders") | Proposed | 🤖 | The "unsaved and parked" lesson (`grid_task_guard.py`) holds for the stop; a stop is never an orphan of a crash. The runtime codec (`bots/application/kinds/grid/grid_runtime_codec.py`) gains an optional field: a state file without it reads as "no stop", which is the truth for every bot saved before |
| D6 | **Cancel only after flat, and "flat" is the account's symbol, not the bot's share.** A `closePosition` order closes the whole symbol, so the stop is cancelled only when `get_positions(symbol)` reads **zero** (the exchange's number) *and* the bot's derived position is zero. A read that fails, or a position left because the close failed, **keeps the stop**. The cancel is one more step of the stop sequence after `PositionExposureCloser.close` returns `None`, not a decorator that can be skipped; a cancel that answers "unknown order" (`-2011`) or finds the order `EXPIRED`/`CANCELED` counts as done | Proposed | 🤖 | A close that fails leaves the stop standing; "cancel first" is the test that must go red. The same read-before-act applies to a reconcile that finds a stop with no position (D7) |
| D7 | **The restart rules** (one table, §3.2): a position with a matching stop adopts it; with none, the bot re-places it, and if the stop cannot be placed (refused, or the trigger is already beyond the market) it **closes the position reduce-only** and says so; a stop with no position is cancelled once a fresh read confirms flat; a stop that triggered while the app was down returns the bot `STOPPED` flat with the reason `protective_stop_triggered`. A stop found that does not equal the plan's is **replaced** (new one stands, then the old one is cancelled), never cancelled first | Proposed | 🤖 | The bot is never bare at any step of a restart, and never leaves a stop that could open a position |
| D8 | **A stop that vanishes while a position stands is re-placed** (once per detection, then closed on failure), whatever the cause: the exchange's `EXPIRED` for a position that passed through zero (⚠️ T2), a cancel by the owner on the exchange's web page, the desk's Emergency Stop. The bot detects it from `ALGO_UPDATE` and from the reconcile's open-order read | Proposed | 🤖 | The design does not depend on how T2 turns out: if the exchange keeps the stop through zero it is simply never missing; if it expires it, the bot re-arms after the next opening fill. The cost is one more order per re-arm and a `PROTECTIVE_STOP_MISSING` event the alert module turns into `STOP_FAILED` |
| D9 | **Neutral places both a SELL and a BUY stop-loss** (one-way mode, `closePosition`): the SELL protects a net long, the BUY a net short. Until the testnet check T3 is recorded (a triggered close-all on the side with no position does nothing and does not open one), a Neutral Futures bot is **unprotected** in the sense of D10 and halts by closing. Long and Short place one stop each | Proposed | 🤖 | Neutral needs T3 because a wrong guess opens the opposite position (the warning of 026K). Not placing the second stop is the safe default; Long and Short never need T3 |
| D10 | **The halt policy (C3):** `closes_on_halt` becomes a question about the *moment of the halt*: the executor reads the open algo orders; a position stays open only if its protective stop(s) read as `NEW` and match the record; every other case (no stop, a stop that cannot be read, a Neutral without T3, a take-profit-only record) closes as today. A halt that cannot send an order (switch-off, rejected key, rate limit) leaves the position and the words say whether a stop stands | Proposed | 🤖 | Fails closed: an unreadable exchange is "not standing" |
| D11 | **The desk's Emergency Stop closes the positions, then cancels the algo orders (C3).** `EmergencyStopCommandHandler` cancels today before it closes; for a conditional `closePosition` order it reverses the order so a failed close leaves the stop. A stop left standing after a *failed* close is reported in the result | Proposed | 🤖 | Changes a `trading` use case that closes every position; unit-tested with a close that fails. Needs no owner question: the stop is cancelled once flat, the same rule as D6 |
| D12 | **The mainnet gate is a record the owner writes, read through a port; the code default is closed (C4).** `CLOSED_VENUES` goes; `bots/contracts` gains the port `IVenueOpening` (`is_open(venue) -> bool`), whose adapter reads a small file only a deliberate command writes (O2). The soak checklist is `Docs/OPERATIONS/futures_testnet_soak.md`; the task opens nothing. The headless host asks the profile: `IShutdownPolicy` gains a `Futures`-aware variant of `LeaveOrdersResting` that refuses to leave a Futures bot with no standing stop (O12) | Proposed | 🤖 (wording of the command: O2) | The gate is configuration, not code; removing the set and adding the port is one commit (the task's own rule) |

## 3. The design in two tables

### 3.1 One protective order's life (each protective order; the machine is per order)

| State | Meaning | Left by |
| :--- | :--- | :--- |
| `ABSENT` | no record | `intend` (a position stands, a stop-loss price exists) |
| `INTENDED` | id and trigger price saved, request not (known to be) accepted | `accepted` → `STANDING`; `rejected` → `ABSENT` + close (D7); `lost_answer` → read by `clientAlgoId` |
| `STANDING` | `NEW` on the exchange | `triggered` → `TRIGGERED`; `cancel_after_flat` → `CANCELLING`; `expired` or `missing_with_position` → `ABSENT` + re-place (D8) |
| `CANCELLING` | cancel sent after a confirmed flat | `cancelled` or `unknown_order` → `ENDED` |
| `TRIGGERED` | the exchange closed the position | `settled` (flat confirmed, sibling cancelled) → `ENDED` |
| `ENDED` | terminal; the record is dropped on the next save | — |

The code will declare this as a transition table in `bots/domain/grid/` (`code/quality.md` §3); `state-machines.md` renders it from there (generated), as it does for the other two machines. Until then the table above is the design.

### 3.2 What a reconcile does with (position, stop)

| Exchange position on the symbol | Protective order on the exchange | The record | Action |
| :--- | :--- | :--- | :--- |
| ≠ 0 | standing, equals the plan | any | adopt; save `STANDING` |
| ≠ 0 | standing, differs from the plan | any | place the plan's stop, then cancel the old (never the reverse) |
| ≠ 0 | none | `STANDING`/`INTENDED` | re-place; on failure close the position and say why |
| ≠ 0 | none | none (old state, or the app died before D5) | place; on failure close |
| 0 | standing | any | orphan: confirm flat with a second read, then cancel |
| 0 | `TRIGGERED`/`FINISHED` | `STANDING` | the bot returns flat: cancel its ladder (without any stop), `STOPPED`, reason `protective_stop_triggered` |
| 0 | none | any | nothing; drop the record |
| read failed | — | — | do nothing, stay `RECOVERING`, say why |

## 4. Alternatives considered

| Alternative | Why it lost |
| :--- | :--- |
| Wait for `EPIC-026K` | It has no code and a different shape (per-entry, strategy-owned); the owner decided to build now (D1) |
| A `quantity` + `reduceOnly` stop sized to the bot's own position | Right for "the bot closes only its own" (owner, 2026-10-13), but the quantity goes stale at every fill: a larger position is under-protected, a smaller one risks a rejected trigger; keeping it equal means a cancel/replace per fill, which is the order-rate cost and the failure window this task removes. `closePosition` plus the existing foreign-position refusal (start) keeps the stop simple; the cost (§5, R2) is named |
| A new id shape for stops (`SEW-{tag}-s…`) | Changes the one pattern every reconcile uses to attribute orders; type and `closePosition` already tell a stop from a ladder order |
| `countdownCancelAll` as a dead man | Cancels orders when the app is gone, the opposite of a protective order; the page does not say it spares conditional orders (⚠️) |
| Trigger on last price (the desk's choice) | The desk judges its own stop on last price (`futures_algo_order_mapper.py` → `_WORKING_TYPE_LAST_PRICE`); the bot's job is liquidation distance, judged on mark |

## 5. Risks this design carries (named, not hidden)

| # | Risk | Mitigation, or why accepted |
| :-- | :--- | :--- |
| R1 | A conditional stop that fires after the bot already closed opens the opposite position (026K's warning) | D6 cancel-after-flat; D7 orphan rule; T3 before Neutral |
| R2 | `closePosition` closes the **whole symbol position**, including one the owner opened by hand after the start | The start refuses a foreign position and the symbol has one owner; a foreign fill already halts the bot. Not narrowed by this design; the stop's words say "closes the whole position on <symbol>" |
| R3 | The mark-price trigger may fire on a mark/last divergence | Accepted (D3) |
| R4 | The desk's cancel-all (Emergency Stop, `cancel_all_orders`) and any manual cancel remove the stop | D11 orders the Emergency Stop; D8 re-places after a manual cancel; `cancel_all_orders` is otherwise a deliberate act |
| R5 | A New Algo Order counts on the 10-second and 1-minute order-rate limits like any order (weight 1 each, 🌐) | A bot places one or two per position and re-arms rarely; the rate-limit pause (`grid_rate_limit_pause.py`) applies |
| R6 | Binance docs partly unread (§1 ⚠️) | T1–T5 are owner testnet runs; D9 and D8 are written so that either outcome of T2/T3 is safe |

## 6. Open questions and the testnet checks (the owner's; never on mainnet)

| # | Question or check | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Does the owner accept D11 (Emergency Stop closes, then cancels the algo orders)? It changes a `trading` use case outside `bots` | C3 | 2026-10-16 |
| O2 | How does the owner open a venue (D12)? Recommended: a state file `venue_opening.json` that only `run`'s new subcommand `open-venue <venue> --confirm <typed phrase>` writes, read through `IVenueOpening`; code default closed. Adds no dependency; **a new settings key would need the owner's approval** (ONBOARDING §7), so the file is not a setting | C4 | 2026-10-16 |
| O3 | The take-profit as an exchange order (D4) doubles the orders per position. Ship it in C2 (recommended: yes, the lifecycle is per order) or leave the take profit in-app only until after the soak? | C2 | 2026-10-16 |
| T1 | On Futures **testnet**: is a `STOP_MARKET closePosition=true` **rejected with no position** at placement? What is the error code? | C2 (the start places it after the opening fill, so a rejection here is the early-warning case) | owner |
| T2 | Does a `closePosition` stop **survive the position passing through zero** and stay `NEW`, or become `EXPIRED`? | C2 (D8 is written to hold either way; the answer sets how often the re-arm runs) | owner |
| T3 | A triggered `closePosition` **BUY** stop while the account is **long** (and the reverse): does it do nothing, or open a position? | C2 for Neutral (D9) | owner |
| T4 | Is the trigger rejected when already beyond the mark (the code and the words)? | C2 | owner |
| T5 | `ORDER_TRADE_UPDATE` vs `ACCOUNT_UPDATE` for one trade, single fills and a burst (handed on by 039D) | C4 soak checklist | owner |

## 7. Implementation evidence

| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [EPIC-039L](incomplete/EPIC-039L_protective_stop_mainnet_gate_and_soak.md) C1 | Verified | the task's Resume and `TRACKING.md` record it |
| D2–D9 | EPIC-039L C2 | Not started | — |
| D10, D11 | EPIC-039L C3 | Not started | — |
| D12 | EPIC-039L C4 | Not started | — |

# BOT-226 — A weight reserve keeps the reads that guard exits served above the 70 % line

**Status:** ✅ Done (2026-10-21)
**Board:** Decision: the venue's gate closes to routine requests at 70 % and to every request at 90 % (owner-delegated, 2026-10-21), and a read named `EXIT_GUARD` on its port (position, mark, open protective stops) is served in between, so a ladder burst cannot leave a stop loss or take profit unjudged ([BUG-247](bug_report/completed/BUG-247_two_wide_grid_ladders_close_the_weight_gate_and_every_read_is_then_logged_as_an_error.md) option C).
**Source:** The owner, 2026-10-21, on `BUG-247`'s option C: "Ok C"; handed to this session by the coordinating session (session_016sGQHsRy729Fp4cY1cTXfu).
**Risk:** 🔴 — real-money behaviour: it changes which requests the gate holds near the exchange's limit; a wrong class lets routine traffic spend the reserve, a wrong hard line risks the exchange's 429 and 418.
**Complexity:** M — three ports, three query handlers, one policy; the classification rides a scoped context because `ITradingClient` stays unchanged.
**Depends on:** `BUG-247` (completed): the connection-check memo that keeps ladder placement itself cheap.

---

## 1. Context and problem
`BUG-247` (`Tasks/bug_report/completed/BUG-247_two_wide_grid_ladders_close_the_weight_gate_and_every_read_is_then_logged_as_an_error.md`, "Safety consequence" and option C): at 70 % of the minute's weight (`ExchangeCallPolicy.note_used_weight`, `SOFT_WEIGHT_RATIO`) the venue's gate closes to everything until the minute turns. While it is closed no bot's position, mark price or open protective stops are read, so its stop loss, take profit and replacement of a missing stop are not judged, for up to a minute, all bots together. Option A (built) cut the cost of ladder placement; option C is the structural answer: a reserve of weight above the line that only those reads may use.

## 2. Acceptance criteria
- [x] Between 70 % and 90 % of the minute's weight, a bot's position read, the symbol's mark read and its open-protective-stops read are sent and answered (unit: real `ResilientSession`, gate and policy; integration: the composed app over the fake exchange).
- [x] In the same band every other request waits as it does today: ladder reads and orders are refused without being sent, with a refusal that says the reserve is kept, not that the exchange asked for a pause.
- [x] At 90 % and above, and during a 429 or a 418, the guards wait too.
- [x] The class is decided at the port and the contract (`RequestPriority` on `IAccountSnapshot.open_positions`, `IOrderEntryTerms.mark_price_for`, `IAccountActivity.open_orders`), not by a list of call sites; only the three query handlers open the scope (architecture guard).
- [x] The reserve is told once when it begins, again if the hard line then closes everything, and its end once; a guard passing the reserve does not announce the pause over.
- [x] The owner's caps (150 open orders, 60 orders a minute, 250 ms spacing) and every order and cancel path are untouched.

## 3. Design
- **Pattern.** Two thresholds on one token-bucket-like window the exchange already reports (a soft and a hard limit with priority classes, as load-shedding does): `RequestPriority.ROUTINE | EXIT_GUARD` (`trading/contracts/request_priority.py`). `RateLimitGate` gains a second deadline that closes the gate to routine requests only (`block_routine`, `routine_remaining`); `ExchangeCallPolicy.note_used_weight` sets it between `SOFT_WEIGHT_RATIO` (0.7) and `HARD_WEIGHT_RATIO` (0.9, new) and sets the existing deadline at or above the hard line. A 429 or 418 still uses the existing deadline, which holds every class.
- **Classification at the port.** Each of the three ports takes `priority: RequestPriority = ROUTINE`; its service puts it on the query (a field with a default); the query handler opens `prioritised(query.priority)` around its one client call. The session sits below `ITradingClient`, whose implementers a parameter would change, so the carrier is a `ContextVar` scope; `ExchangeCallPolicy._run` reads `current_priority()` once per call. The bots side names `EXIT_GUARD` in the four places the three facts are read for exits: `BotAccountReads.position` and `protective_orders`, `read_mark_price`, and `SharedPositionReads`.
- **Rejected.** A list of guarding client method names in the session (`futures_position_information`, ...): the same method serves ladder reconciliation (open orders) and screens, so a name cannot tell a guard from a routine read. A priority parameter on every `ITradingClient` method: nine implementers for one policy.
- **Reserve size (owner-delegated decision, 2026-10-21).** The owner approved option C ("Ok C") without a size and then handed the figure to the coordinating session ("tự quyết đi" = decide it yourself); the coordinator decided **`HARD_WEIGHT_RATIO` = 90 %**. Figures (Futures, 2,400): the guard spend of an idle minute is 96, 240 and ~780 weight at 1, 5 and 20 bots (measured, `test_many_bots_on_one_venue_cost_on_the_fake_exchange.py -k "measured and idle"`) and the cap is five bots, so about 240 a minute at the cap. Alternatives: **85 %** (2,040; reserve 360, buffer 360) still covers the cap with 120 to spare but leaves less for a pause that begins at the top of the minute; **95 %** (2,280; reserve 600, buffer 120) is too close to the ~100-weight chains `BUG-216` saw in flight when a header crossed. 90 % covers the cap with room and keeps 240 under the exchange's limit. It is one constant, reversible; the argument is in `HARD_WEIGHT_RATIO`'s comment and `06-runtime.md` limit (4).

## 3a. Reuse
`RateLimitGate`, `ExchangeCallPolicy`, the query handlers and the port services: extended, not replaced. `WeightMeter` and `booted_two_venues` (the fake exchange): used for the journey. No UI or application need beyond that: `.claude/rules/capabilities.md` has no row for request weight or rate limits (its catalog scans `src/support`, `src/core` and `src/shell`, not a module's contracts), so nothing existing fits and `RequestPriority` is declared in the Vocabulary instead.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/request_priority.py` (new) | `RequestPriority`, `prioritised`, `current_priority` |
| `src/modules/trading/adapters/binance/rate_limit_gate.py` | the routine-only deadline |
| `src/modules/trading/adapters/binance/exchange_call_policy.py` | `HARD_WEIGHT_RATIO`, the two lines, the priority-aware check, the reserve's log lines |
| `src/modules/trading/contracts/i_account_snapshot.py`, `i_account_activity.py`, `i_order_entry_terms.py` and their services | the `priority` parameter |
| `src/modules/trading/application/queries/get_open_positions`, `get_open_orders`, `get_mark_price` | `priority` on the query; the handler opens the scope |
| `src/modules/trading/contracts/testing/` (three fakes) | accept and record the priority |
| `src/modules/bots/application/services/orders/bot_account_reads.py`, `risk/shared_position_reads.py`, `venue/mark_source_futures.py` | name `EXIT_GUARD` for the exit facts |
| `Docs/MODULES/bots/06-runtime.md`, `Docs/VOCABULARY/README.md` | the design and the words |
| `tests/` | see §5 |

## 5. Testing
- Unit, policy and session: `tests/unit/modules/trading/adapters/binance/test_the_weight_reserve_serves_the_reads_that_guard_exits.py` (guards pass in the reserve; routine waits and is not sent; hard line and 429 hold the guards; the minute turning; the log lines).
- Unit, ports and handlers: `tests/unit/modules/trading/application/queries/test_the_read_priority_reaches_the_client.py`; bots: `tests/unit/modules/bots/application/services/test_the_reads_that_guard_exits_say_so_at_their_ports.py`.
- Architecture: `tests/unit/architecture/test_only_the_query_handlers_open_a_request_priority_scope.py`.
- Integration, composed app on the fake exchange: `tests/integration/modules/bots/test_the_weight_reserve_keeps_the_exit_guards_reading_on_the_fake_exchange.py`.
- Existing tests moved: `test_exchange_call_policy.py` and two policy files used 75 % of the limit to mean "the gate is closed to everything"; that is now 92 % (the hard line), and the 70 % case asserts the routine deadline. Test doubles of the three ports take the new parameter.
- Mutation-verified by hand: the policy treating a guard as routine (7 red), a routine as a guard (4 red), a handler dropping the priority (red), the stops read as routine (red).

## 6. Docs touched
`Docs/MODULES/bots/06-runtime.md` ("Built: several bots on one venue", the reserve bullet); `Docs/VOCABULARY/README.md` (exit guard, weight reserve).

## Implementation notes (written when done)
Delivered in PR #690 (head `d7a0602`); the task was filed as BOT-224 and renumbered BOT-226 when #689 took that id.

- **Built as designed (§3, §4).** `RequestPriority` on the three ports, carried by a `ContextVar` scope the three query handlers open; `RateLimitGate.block_routine` / `routine_remaining`; `ExchangeCallPolicy` closes to routine requests at `SOFT_WEIGHT_RATIO` (70 %) and to every request at `HARD_WEIGHT_RATIO` (90 %). The bots name `EXIT_GUARD` in `BotAccountReads.position` / `protective_orders`, `read_mark_price` and `SharedPositionReads`.
- **Decision: 90 %.** The owner approved option C without a size and delegated the figure to the coordinating session on 2026-10-21; it decided 90 %. Measured guard spend of an idle minute is 96 / 240 / ~780 weight at 1 / 5 / 20 bots against a 480 reserve, and the cap is five bots. Alternatives 85 % (reserve 360, buffer 360) and 95 % (reserve 600, buffer 120). One constant, reversible.
- **Review round 1 (NEEDS_REVISION, gate green) changed three things:** the BUG-217 regression test regained its original 75 % path; the reserve and the pause that closes every request are announced apart, each with its own end (a 429 inside the reserve was told with the reserve's end); a guard locks which files may name `EXIT_GUARD`. The generated timing row of `Docs/MODULES/bots/10-quality.md` states both lines. Rounds 2 to 4: PASS.
- **Existing tests moved:** the policy tests that used 75 % of the limit to mean "closed to everything" use 92 %; test doubles of the three ports take the new parameter.
- **Mutation checks by hand (all red):** a guard treated as routine, a routine read treated as a guard, a handler dropping the priority, the stops read as routine.
- **Evidence.** CI run 39602930032 on `d7a0602`: `gate (Unit)` (job 119232446921) and `gate (Rest)` (job 119232446533) `RESULT: PASS`, `FAILED_STEPS: none`, no `FAILED` / `Traceback` / `ResourceWarning` / WARNING-ERROR record in either job log. Reviewer's round 4 comment: https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/690#issuecomment-6316451089.
- **Limits left (also in `Docs/MODULES/bots/06-runtime.md`).** The run host's coverage read (`StopCoverageReader`, a ladder read) answers "unread" in the reserve; the reserve covers the five-bot cap, not 20; the optional journey with a booted bot reading through the reserve was not added.

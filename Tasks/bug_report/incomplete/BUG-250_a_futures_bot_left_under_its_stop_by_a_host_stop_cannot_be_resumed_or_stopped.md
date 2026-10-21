# BUG-250 — A Futures bot a host stop left under its protective stop cannot be resumed or stopped: "The account has unexpected open positions"

- **Reported:** 2026-10-21 (the delivery coordinator, from the owner's VPS on Futures Testnet, master `849d9736`)
- **Severity:** 🔴 P1 — two live Futures Grid bots (`6tszoz` ETHUSDT, `6z20d2` BNBUSDT) are stuck RECOVERING with 131 orders resting and a position each; the only way back (decision O2, the bot's own Resume) and the only way out (`bot stop --close-position`) are both refused, so the runs are lost unless the positions are closed by hand
- **Status:** Open
- **Board:** A restart after the host's default stop leaves a Futures bot RECOVERING under its position, and Resume is refused with "The account has unexpected open positions" because the closed order session refuses every position, the bot's own included
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (run a Grid bot; restart and recovery) → `src/modules/trading/` (`application/session/`) and `src/modules/bots/` (`application/kinds/grid/`, `application/services/orders/`) → application layer
- **Environment:** Linux VPS, `sew-update`, unit args `run --on-stop leave-orders --start-planned --resume-halted ...`, master `849d9736`, Futures Testnet. Reproduced on `27e1ae1` on the composed app over the fake Futures exchange (the first test below, red before the fix).

## Reproduction
1. Two Futures Grid bots (a LONG on `BTCUSDT`, one on `ETHUSDT`) run, each with a position under its protective stop and a ladder resting.
2. The host stops with the default `--on-stop leave-orders` (`EPIC-038M`, O12): the stop covers each position, so both are left as they are.
3. The app starts again: the order session is closed and both bots are RECOVERING (decision O2: a person resumes them).
4. `main.py bot resume <id>` (or the Bots tab's Resume, or `run --resume-recovering`).
Expected: the session opens over the bot's own position, the bot adopts its ladder and position and returns to RUNNING. Actual: refused, the bot stays RECOVERING. Always.

## Symptom
```
[stop-policy] leave-orders: leaves 6tszoz (RUNNING) 48 orders resting; its stop covers its position (its protective stop stands on the exchange)
[stop-policy] leave-orders: leaves 6z20d2 (RUNNING) 83 orders resting; its stop covers its position (its protective stop stands on the exchange)
[recovering] bot 6tszoz (ETH_FUTURE_TEST_48) is RECOVERING after the restart and stays so: a person resumes it (decision O2) - `main.py bot resume 6tszoz` ...
$ M bot resume 6tszoz
bot resume 6tszoz: The account has unexpected open positions — please handle them manually on the exchange before starting a bot, arming a strategy or placing an order.
$ M bot resume 6z20d2
bot resume 6z20d2: The account has unexpected open positions — please handle them manually on the exchange before starting a bot, arming a strategy or placing an order.
```
The positions are the bots' own (ETHUSDT long about 0.3, BNBUSDT long), each covered by the bot's protective stop.

## Root cause
At `27e1ae1`: `SessionReadiness._ensure_ready_serialised` (`src/modules/trading/application/session/session_readiness.py:126-134`) reads every position of the account when it opens a closed order session and returns `SessionBlockReason.UNEXPECTED_POSITIONS` for any one of them (`if positions:`), because "this app never auto-adopts or auto-closes a position it did not open itself". A restart always leaves the session closed. Every deliberate bot action that opens it goes through `order_session_refusal` (`src/modules/bots/application/services/orders/order_session_opening.py:64-71`): Start, a Resume from HALTED or RECOVERING (`BotRunner.resume` → `GridStartPreconditions.open_session_for_resume`, `bot_runner.py:112-115`; the Bots tab's Resume, `bot resume` and `run --resume-recovering` all end there), and the operator's `bot stop` (`stop_bot_for_operator/handler.py:129`). The opening has no way to say "this position is a bot's own", so the policy that leaves the position (O12, `EPIC-038M`) and the only remedy for a left bot (O2, Resume) contradict each other: the design leaves a bot that can never be resumed, and `bot stop --close-position` is refused for the same reason.

The ownership facts exist, but only after the session is open: the budget registration derives a Futures owner's position from the venue's history of its tagged orders and refuses a foreign one (`OwnerPositionRegistrar.derive_and_install`, `FOREIGN_POSITION`). The opening ran before it and used none of them.

Why the gate was green: `booted_futures_bots` and `booted_two_venues` seed the session open by default, so every restart journey (`test_a_restart_in_the_middle_of_the_ladder_recovers_its_orders_and_its_position`) emitted the switch event over an already-open session and never met the opening's refusal. Not filed as a case study: the closing net is the new closed-session restart journey (below); the blind spot "a world that seeds the session open skips the opening's own refusals" is named for the coordinator in the pull request.

## Fix
The bot names whose history to read; trading decides from the exchange's evidence.
- `src/modules/trading/contracts/owner_position_claim.py` → `OwnerPositionClaim` (owner id, tag, symbol, run start; no figure); `OwnerBudgetRegistration` is now a claim that also carries a budget, so the one derivation serves both.
- `ITradingSession.ensure_ready(opened_for, claims)` → `EnsureSessionReadyCommand.claims` → `SessionReadiness`, which asks `PositionExplainer` (`src/modules/trading/application/session/position_explainer.py`) about every position the account holds. A position is excused only when a claim on its symbol is backed by `OwnerPositionDeriver` (the tagged order and trade history since the run started, which also counts fills that landed while the host was down) within one quantity step. A symbol no claim names, a quantity the history does not explain (more, less, the other side), and a history that cannot be read all refuse, with `SessionReadyResult.unexplained_positions` naming the symbol and both figures in `refusal_words`. The excused symbols seed `known_open_symbols`.
- `src/modules/bots/application/kinds/grid/grid_position_claims.py` → `venue_position_claims`: the claims of every mid-run bot of the venue (the opening is venue-wide, so the first Resume needs every waiting bot's position explained). Only `GridStartPreconditions.open_session_for_resume` (every Resume) and the operator's Stop pass them; Start, Arm strategy and a manual order pass none and refuse every position as before. Spot, with no positions, is never read.
- The store's rule is kept: the bot's file is never an input to the check, only the name of whose history to read, so a hand-edited file cannot excuse a foreign position.
- Not changed: O12's close-or-leave policy, the host's stop, the registration's own checks (`FOREIGN_POSITION`, `POSITION_MISMATCH`), which still run after the opening.

## Regression test
`tests/integration/modules/bots/test_a_recovering_futures_bot_resumes_under_the_position_a_host_stop_left_on_the_fake_exchange.py` — on the composed app over the fake Futures exchange, two bots on two symbols, a real restart with the session closed:
- `test_a_recovering_bot_resumes_and_adopts_its_ladder_and_its_position` — failed before the fix with the owner's verbatim refusal (`The account has unexpected open positions — …`), passes after; the second bot keeps waiting until its own Resume.
- `test_a_position_no_bots_history_explains_still_refuses_the_resume`, `test_more_than_the_bots_own_history_explains_on_its_symbol_still_refuses_the_resume` — a stray symbol and a size beyond the tagged history refuse in words naming the symbol and quantities (the wording part red before).
- `test_the_operators_stop_of_a_recovering_bot_closes_its_position_through_the_same_opening`, `test_a_start_still_refuses_while_a_position_stands_that_it_does_not_own`, `test_spot_is_unaffected`.
Unit: `test_position_explainer.py` (14: tolerance at one step, short side, fills while down, unreadable history, history older than the venue keeps, one explained symbol never excuses a stray beside it), `test_session_opens_over_a_claimed_position.py`, `test_grid_position_claims.py`, `test_bot_runner_resume.py` and `test_grid_start_preconditions.py` (a Resume passes the venue's claims, a Start none).

## Verification
Mutation-checked: dropping the tolerance comparison, widening it 100x, excusing an unverifiable history, taking the absolute derived quantity, dropping the no-claim branch, and a Resume that passes no claims each turn the matching tests red. Positive proof the mechanism ran: the integration test asserts the `[position-claim]` "excused" line for both symbols from `App.TradingSession`. The `ci-local.ps1 -Full` run on the pull request's head is the full-gate authority and is read from its job logs. Not verified: a real exchange (Futures Testnet VPS); the owner's two bots.

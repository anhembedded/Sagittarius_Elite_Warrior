# EPIC-035E — Symbol status gates placement

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M5 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — placing on a halted symbol fails into ERROR instead of a named pause
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit M5: the symbol status (TRADING, BREAK, HALT, CANCEL_ONLY, and a delisting) is parsed but nothing reads it; `src/modules/trading/adapters/binance/spot/spot_metadata_parser.py:160` has no consumer. The bot keeps submitting, is rejected and goes to ERROR; `CANCEL_ONLY` was introduced on 2026-07-07 (audit's source). Verify the parser line and the absence of a consumer by `grep` first.

**Claim verified ✅ on `be67b47`, with two refinements.**
- `spot_metadata_parser.py:160` reads the status into `SymbolOrderMetadata.status`; `grep` for a read of `.status` on rules or metadata finds none in `src/`. The bots module's `ExchangeTerms` did not carry it.
- The refusal reaches the bot as `OrderRejectedByExchangeError`, which `BotOrderGateway._submit` caught only as a bare `Exception`: a FAULT, so ERROR, whose exit is Stop. Reproduced red before the change (the three tests that go through it ended `ERROR`).
- Refinement 1: a payload with no `status` field is read as `TRADING` (`DEFAULT_STATUS`, parser line 66). Binance always sends it, so it is left; an absent status is not a delisting.
- Refinement 2: trading answers the status from its **cached** symbol catalog (24 h), so a status that changed minutes ago reads TRADING until `EPIC-035U` refreshes it. The task's own Design says so; the exchange's refusal of the next order is what pauses the bot in the meantime.

This task is specified briefly: it is Phase 2 — Infrastructure resilience. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [x] Exchange terms carry the symbol status through the bots module's exchange-terms seam: `ExchangeTerms.symbol_status` (default `TRADING`, so no call site breaks) filled by `exchange_terms_for`. Evidence: `test_the_symbols_status_is_carried_to_the_terms`.
- [x] Placement is gated on status TRADING, with a named reason: `SymbolStatusGate.admits()` before a Start (refused, `symbol_not_trading`, nothing sent), before a confirmed Resume and before a Resume from PAUSED; an order the exchange refuses for the status PAUSEs a RUNNING bot (the order and every order still owed are held, the ladder keeps resting); a symbol the exchange no longer lists, or an order refused as an unknown symbol, HALTs it (`symbol_delisted`) and the guard takes the ladder off. Evidence: `test_a_symbol_in_break_pauses_the_bot_with_a_named_reason` (red: ERROR), `test_a_symbol_that_does_not_trade_refuses_the_start_before_any_order` (red: RUNNING, orders sent), `test_a_delisting_halts_the_bot` (red: ERROR), `test_a_refusal_for_the_status_while_starting_halts_by_name` (red: ERROR). **Deviation, stated:** "PAUSE before a submit is attempted" holds for Start and Resume. Mid-run the status is only known once the exchange refuses an order, until `EPIC-035U` feeds it; one order is therefore attempted, refused and held. The translator's text matches (`Market is closed.`, `not trading`, `-1121`) come from Binance's documentation and are **not verified against a live answer** (egress to the exchange is blocked here).
- [x] A bot paused for status resumes only by the user, after the status is TRADING again; the status is shown on the bot: nothing resumes it; Resume re-reads the status and, while it is not TRADING, leaves the bot PAUSED with "BTCUSDT is BREAK on the exchange; resume once it is TRADING" in its detail (the bots screen's state line). Evidence: `test_a_bot_paused_for_the_status_does_not_resume_while_it_persists`, `test_a_bot_paused_for_the_status_resumes_once_it_trades_and_places_what_it_held`, `test_a_refusal_for_the_status_while_resuming_pauses_again_and_keeps_the_orders`.
- [x] In CANCEL_ONLY the bot still cancels on Stop: the gate is not asked by a stop. Evidence: `test_cancel_only_still_allows_stop` (a lock; it passed before the change too, because nothing consulted the status).

## 3. Design
The terms refresh of `EPIC-035U` is the feed that keeps the status current; until it lands, the status is read at Start and when an order is rejected with a status-class error.

Built as one collaborator, `SymbolStatusGate` (`symbol_status_gate.py`), reached from `GridExecutor._run_start`, `_run_resume` (PAUSED) and `GridResumeSequence.confirm`; `GridExecutor` gained no method and no public surface. The refusal path is the gateway classifying `OrderRejectedByExchangeError` by its named reason (`SYMBOL_NOT_TRADING`, `SYMBOL_NOT_LISTED`, new members of trading's closed `OrderRejectionReason`) into two new outcome kinds; any other rejection stays a FAULT. `GridLadderPlacer` is where a RUNNING ladder pauses, because only there are the owed orders in hand to hold (`hold_order` in the domain reactions). The reasons follow the `PRICE_FEED_STALE` / `USER_STREAM_DOWN` pattern: `GridReason.SYMBOL_NOT_TRADING` and `SYMBOL_DELISTED`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/bot_exchange_terms.py` | carries the status into `ExchangeTerms` |
| `src/modules/bots/domain/bot_kind_inputs.py` | `ExchangeTerms.symbol_status`, `trades` |
| `src/modules/bots/application/services/symbol_status_gate.py` (new) | the gate |
| `src/modules/bots/application/services/{grid_executor,grid_resume_sequence,grid_run_context}.py` | the three call sites; `LazyExchangeTerms.refresh()` |
| `src/modules/bots/application/services/{bot_order_gateway,grid_order_failure,grid_ladder_placer}.py`, `domain/grid/{grid_reactions,grid_runtime}.py` | the refusal for a status is a named outcome, a pause that holds the owed orders, or a halt |
| `src/modules/trading/contracts/order_rejection_reason.py`, `adapters/binance/binance_error_translator.py` | two named reasons and where they come from |
| `src/modules/trading/adapters/binance/spot/spot_metadata_parser.py` | unchanged: it already parses the status; the consumer was missing |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | two rows in §5, one in §8 |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Unit tier, real executor through the real factory on the simulated venue, in `tests/unit/modules/bots/application/services/test_grid_symbol_status.py` (nine tests: seven observed red before the change, ERROR where a test names PAUSED or HALTED and RUNNING with orders sent where it names a refused start; the other two, `test_cancel_only_still_allows_stop` and `test_any_other_refusal_that_raised_is_still_a_fault`, are locks of behaviour that already held), plus the translator rows and `test_the_symbols_status_is_carried_to_the_terms`. Green after: those, `tests/unit/modules/bots` and `tests/integration/modules/bots` (1427 tests).

## Implementation notes
- Not built, by design: a per-fill status read (a network read each time) and an auto-resume when the symbol trades again (the criterion says only the user resumes).
- The Futures venue's other status strings (`PENDING_TRADING`, `SETTLING` …) are refused by the same rule (anything but `TRADING`); a Futures grid does not exist yet (`EPIC-029K`).

## Resume
Done. Nothing owed.

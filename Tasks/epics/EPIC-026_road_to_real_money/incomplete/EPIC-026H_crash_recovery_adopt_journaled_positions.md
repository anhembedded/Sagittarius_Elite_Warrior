# EPIC-026H — Crash recovery: a position the journal recorded as ours is adopted on enable, a foreign one is still refused

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.2 row 1 and ADR `❓ O2`; the user
(2026-09-20): *"hãy cho lô trình để có thể giao dịch thật"*.
**Risk:** 🔴 — changes the one refusal that protects the account from adopting a stranger's
position; a wrong match adopts money that is not the strategy's.
**Complexity:** M — one handler, one matching rule, one new block reason; the difficulty is the
rule's proof, not its size.
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** updates `SPEC-004` §3 step 5 and §5 (`UNEXPECTED_POSITIONS` splits in two).
**Depends on:** [`EPIC-026G`](EPIC-026G_trade_journal.md); ADR `O2` answered (adopt, as
recommended, or refuse as today — if the user chooses refuse, this task closes as Cancelled with
the reason at its top).

---

## 1. Context and problem

`EnableTradingCommandHandler` reads positions and refuses if any exist
(`session/enable_trading/handler.py:119-125`, `EnableTradingBlockReason.UNEXPECTED_POSITIONS`).
That was right when the app had no memory. With a journal, "unexpected" has two cases: a
position this app opened before it died (the strategy that planned the exit should resume), and
a position someone else opened (still refuse, still do not close). Today both are refused, so a
crash with an open position forces the operator to close by hand on the web UI — with real money
the cost of that minute is the point of this task.

## 2. Acceptance criteria

- [ ] On enable, each exchange position is matched against `ITradeJournal.open_positions_believed()`
      by `(venue, symbol, side)` **and** by quantity within one lot step; a match is adopted:
      `known_open_symbols` seeded, the symbol lease re-claimed for the journaled owner if it was a
      strategy's, and `EnableTradingResult.adopted_positions` lists it.
- [ ] A position with no match, or a quantity mismatch beyond one lot step, still refuses with
      `UNEXPECTED_POSITIONS` — and the result names *which* positions matched and which did not.
- [ ] An `intent` row with no outcome (`EPIC-026G`) is resolved first by querying the exchange for
      that client order id (`EPIC-026I`'s query); only then is matching run.
- [ ] Adoption is journaled as its own row, so `EPIC-026O`'s reconciliation can see it.
- [ ] `SPEC-004` §3 and §5 updated in the same pull request; the human row re-run: kill the app
      with one open Testnet position, restart, enable, see it adopted with its stop still present
      (`EPIC-026K`) or re-placed.

## 3. Design

The matching rule is a pure domain policy, `PositionAdoptionPolicy.match(exchange_positions,
journaled_positions, lot_steps) -> AdoptionDecision`, in `trading/domain/policies/` beside
`trading_limit_policy.py`, unit-tested on every branch before the handler calls it
(`fix-bug-rule.md` §4's discipline applied to a feature: the red test first is the mismatch case).
The handler's concurrency rule (`BUG-088`'s generation check) is untouched: adoption happens
inside the same guarded step as today's reconciliation.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/trading/domain/policies/position_adoption_policy.py` | New pure policy |
| `src/modules/trading/application/session/enable_trading/handler.py` | Resolve intents, run the policy, adopt or refuse |
| `src/modules/trading/contracts/enable_trading_result.py` | `adopted_positions`, `foreign_positions` |
| `src/modules/trading/ui/trading/trading_presenter.py` | Show adopted and foreign separately |
| `Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md` | §3 step 5, §5 rows, §8 rows |
| `tests/unit/modules/trading/domain/policies/test_position_adoption_policy.py` | Every branch |
| `tests/unit/modules/trading/application/session/test_enable_trading.py` | Adopt, refuse, mixed, intent-first |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Policy branches | policy unit test | unit | match, side mismatch, quantity beyond step, no journal |
| Handler | `test_enable_trading.py` extended | unit | adopted seeds symbols and lease; foreign refuses; both reported |
| Concurrency kept | existing generation-check tests still green | unit | green |
| Human | kill with an open position, restart, enable | human | adopted, reported, stop present |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)

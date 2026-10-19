# BUG-225 — A live Grid fill delivered before the fill of the rung its counter goes to halts the bot with `DUPLICATE_LEVEL_ORDER` (and a Futures bot closes its healthy position)

- **Reported:** 2026-10-18 (owner, VPS journal of bot `Future_BTC_TestNet` / `sj9rno`, 13:26:57 UTC; the journal itself was not readable by the author session)
- **Severity:** 🔴 P1. Real-money path on Futures: the halt closes a healthy leveraged position at market. Money-safe in the sense that the bot ends flat with no orders, but it realises a loss when nothing was wrong.
- **Status:** ✅ Fixed (2026-10-19)
- **Board:** A Grid halted with `DUPLICATE_LEVEL_ORDER` when the price fell through two adjacent BUY rungs and the lower rung's fill was applied before the higher one's. Cause (hypothesis for the VPS, proven on the fake exchange): the live path applies fills in stream delivery order and `_counter` finds the higher rung's still-unapplied BUY on the counter's level. Fix: before halting, `GridBlockedCounter` reads that order once from the exchange; a filled one parks the counter until its own fill is applied, a cancelled one frees the level, an open one still halts.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), a running Grid meets a fast fall → `bots` → `domain/grid/grid_reactions.py` (`_counter`), `application/kinds/grid/` (`GridFacts`, new `GridBlockedCounter`)
- **Environment:** VPS (Futures Testnet, BTCUSDT, LONG) at an unrecorded commit; reproduced on the Spot and Futures testnet fakes at `55750f6` (master-warrior). Not run on a live exchange.

## Reproduction
1. Start a Grid (Futures Long 62,000–66,000, 4 grids; or the Spot ladder).
2. The price falls through two adjacent BUY rungs (63,000 then 62,000); the stream delivers the 62,000 fill before the 63,000 one.

Expected: both fills applied, bot RUNNING, counters laid. Actual: HALTED `duplicate_level_order`; Futures then closes the position at market.

## Symptom
Incident (owner's report): `duplicate_level_order`: "L7 already holds an order; the counter of L6 cannot go there". Reproduced on the fake exchange before the fix:
```text
Bot 86n5eg: RUNNING -> HALTED on halt (duplicate_level_order: L1 already holds an order; the counter of L0 cannot go there) [bot-transition]
Bot 86n5eg: halted (duplicate_level_order); closing the position [halt-closes-position]
```

## Root cause
**Established on the fake exchange; the VPS journal (relayed by the coordinator session, 20:26:22-20:26:57 local = UTC+7) agrees with it.** The price whipsawed across the L7/L8 band every 1-3 s with ~20 fills; the derived position lagged the exchange's REST position by about a second (`position_mismatch ... exchange wins`), so fills were applied late. At 20:26:57.659 the counter BUY of an L8 SELL fill took L7; 12 ms later the L6 BUY fill (owing a SELL at L7) was applied and halted. The two fills were applied in the opposite order to the exchange's. Not shown by the journal: whether the fresh L7 BUY had already filled on the exchange; if it was still open, the halt was genuine and this fix leaves it. Earlier wording kept for the record: `GridFacts._apply_fill` (`grid_facts.py`, before the fix) applies each fill in the order the bus delivers it and `on_fill` → `_counter` (`grid_reactions.py`, the `level.state is not LevelState.EMPTY` check) halts when the counter's level still holds an order. A full BUY at level i owes a SELL at i+1; when the BUY at i+1 has filled on the exchange but its report has not been applied, the ledger still holds it. The stream does not guarantee the exchange's order across the two reports (the fake reproduces it by delivering them reversed). This is the live-path twin of `BUG-214`, which fixed only the reconcile (`grid_missed_fills.py`). Why the stream delivered them late is not shown. The journal command used: `journalctl -u sew-run --since "2026-10-18 13:20" --until "2026-10-18 13:28" --no-pager | grep -E "sj9rno|L6|L7"`; the hypothesis holds if the fill of the L6 order appears before the fill of the L7 order (or L7's fill is absent before the halt). If L7's order was in fact still open on the exchange, this fix does not apply and the halt was genuine.

## Fix
- `grid_reactions.py`: `Halt.occupied_level` (defaulted) names the level whose order stood in the counter's way; the pure functions are otherwise unchanged and the halt text is the same.
- New `grid_blocked_counter.py` → `GridBlockedCounter`, called by `GridFacts._apply_fill` instead of `on_fill`: on a blocked counter it reads that order once with `find_order` (uncached; `BotAccountReads.order_status`). **Filled**: the fill that owes the counter is parked and replayed right after the order's own fill is applied, so fills are applied in the exchange's order. **Cancelled / expired / rejected with nothing executed**: the level is freed and the counter retried. **Open, unknown or unreadable**: the halt stands.
- Design choice: parking, not applying the order's fill from history. Trading's owner book learns a fill only from the stream; a counter SELL placed from a history-applied fill is refused as exceeding the inventory the book knows (seen on the Spot fake), and the history reads are cached for 15 s (`CachedAccountHistoryReader`). The alternative (apply from history through `IOrderFillReporter`) is BOT-173's seam and needs the reporter published to the bots; it was not built. A parked fill is in memory only: a restart or a stream gap reconciles from history in the exchange's order (`BUG-214`), and `on_fill` ignores a fill for an order the ledger no longer holds, so nothing is applied twice.
- Other producers of the reason: `GridLadderPlacer._place` ("nothing was sent") is a send-time guard fed by reactions that already passed `_counter`; the new path emits distinct levels, so it stays a genuine guard. `GridReconciler._adopt` ("holds two orders carrying the tag") runs after `GridMissedFills.apply`, which `BUG-214` ordered; a real double tag still halts. `_emit`'s held duplicate ("crossed it both ways while paused") needs the same level twice in `held`, which two buy fills in either order do not produce; but a paused bot whose counter was blocked takes the same read and parking path (`hold` is passed through). All guards intact.

## Regression test
- `tests/integration/modules/bots/test_a_fill_delivered_before_the_fill_beneath_it_on_the_fake_exchange.py`: Futures Long and Spot on the fake exchange, two adjacent BUYs filled, their reports delivered reversed to the real stream handler. Red before the fix with the incident's message; green after.
- `tests/unit/modules/bots/application/services/test_grid_blocked_counter.py`: filled → parked then replayed; cancelled → level freed; still open → halts with the same message.
- Mutation checks: skipping the exchange read turns 4 of the 5 red; skipping the replay turns 3 red.

## Verification
The 5 new tests, `tests/unit/modules/bots`, `tests/unit/modules/trading`, `tests/unit/architecture` and `tests/integration/modules/bots` green locally; ruff and format clean; mypy shows no error in the changed files (the repository's measured baseline is unchanged). Positive proof the mechanism ran: `[blocked-counter] ... which the exchange has filled; parked until that fill is applied` in the green run's log. The full gate is the pull request's `ci-local.ps1 -Full` run. **Not proven:** a live exchange's real delivery order, and the VPS cause.

## Follow-up (not built)
- `BUG-226` (filed Open): the halt's stop path logged `ERROR ... cancel SEW-sj9rno-42338a6e20 raised` for a protective stop already gone once the position was flat.
EPIC-042 decided that Futures auto-recovers no halt reason; making `DUPLICATE_LEVEL_ORDER` auto-recover would be the owner's decision. `BOT-173` (a fill counted from whichever record arrives first) is related, not closed by this: a history read reporting through `IOrderFillReporter` would let the bot apply the order's fill at once instead of parking.

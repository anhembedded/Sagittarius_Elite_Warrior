# EPIC-026O — A journal-versus-exchange reconciliation script, and the 14-day unattended Testnet soak that gate 2 reads

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §2 success criterion 3; ADR D6; the user
(2026-09-20): *"hãy cho lô trình để có thể giao dịch thật"*.
**Risk:** 🟡 — a script and a report; the risk is a soak that "passes" because the script
compares too little.
**Complexity:** M — one script, one drill day, fourteen days of waiting, one report.
**Epic:** [`EPIC-026`](../README.md)
**Depends on:** [`EPIC-026G`](EPIC-026G_trade_journal.md) … [`EPIC-026N`](EPIC-026N_user_data_stream_watchdog.md),
all merged; the candidate from [`EPIC-026F`](EPIC-026F_live_candidate_report.md) (the soak runs
the strategy that will trade for real, or the reference strategy if gate 1 is not yet passed —
the report says which).

---

## 1. Context and problem

Gate 2 is "operations survive without a human". Fourteen days without a human is the only test of
that; the journal is the only record of what the app believed; the exchange's trade history is the
only truth. Nothing today compares the two, and nothing has ever run for two weeks unattended.
`EPIC-021`'s pattern — every task ends in something runnable and visible — is kept: the script is
runnable any day, the report is the visible thing.

## 2. Acceptance criteria

- [ ] `scripts/epic026o_reconcile_journal.py --since {date}` reads the journal and the exchange's
      `userTrades`, `allOrders` and `positionRisk` for the venue and symbol, and prints three
      tables: orders (journal ∖ exchange, exchange ∖ journal, status mismatches), fills (quantity and
      price per client order id), positions (believed vs held). Exit code 0 only on zero
      unexplained differences; an *explained* difference (an adoption row, a stop cancelled by the
      exchange) is listed with its explanation.
- [ ] The soak: the app runs headless (`main.py`'s daemon mode, or the UI on a machine that stays
      on) on Testnet with the candidate armed, trading enabled, breaker and watchdog on, alerts to
      a real channel, for **14 consecutive days**. A restart of the app is allowed and counted; a
      code change restarts the count.
- [ ] Drills on day 1: `breaker-drill` (`EPIC-026L`), `stream-drill` (`EPIC-026N`), a kill of the
      process with an open position followed by `EPIC-026H`'s adoption, a protective stop
      triggered by the fake-price control if Testnet allows it or observed naturally otherwise.
- [ ] `Tasks/reports/soak/{start}_{end}_testnet.md`: the script's final output, the drill logs
      (positive proof lines under each `App.*` logger), every alert received, every restart with
      its cause, the run-log scan (`- (WARNING|ERROR|CRITICAL) -`) with every record explained,
      and the verdict: gate 2 passed or not, and why.

## 3. Design

The script lives in `scripts/` beside `epic021h_user_stream_probe.py` and uses the module's own
ports (`ITradingClient` for the exchange, `ITradeJournal` for the journal) through the
composition root — never the SDK directly (the guard that only the session factory constructs a
`Client` stays green). Reconciliation rules are pure functions in
`trading/domain/policies/journal_reconciliation.py` so the script is thin and the rules are
unit-tested with the verified fakes. The report is prose plus pasted output; no new format.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/trading/domain/policies/journal_reconciliation.py` | Pure diff rules |
| `src/modules/trading/contracts/i_trading_client.py` | `get_user_trades(symbol, since)`, `get_all_orders(symbol, since)` |
| `src/modules/trading/adapters/binance/futures_trading_client.py` | The two reads |
| `scripts/epic026o_reconcile_journal.py` | The script |
| `tests/unit/modules/trading/domain/policies/test_journal_reconciliation.py` | Each difference class; explained vs unexplained |
| `tests/unit/scripts/test_epic026o_reconcile_journal.py` | Exit code and tables against fakes |
| `Tasks/reports/soak/{start}_{end}_testnet.md` | The report |
| `Tasks/epics/EPIC-026_road_to_real_money/README.md` | §4 stage 2 row closed with the link |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Rules | policy unit test | unit | every class of difference produced and named |
| Script | unit against fakes | unit | exit 0 on clean; 1 with a table on any unexplained difference |
| Soak | 14 days on Testnet | human | report with the script's exit 0 on the last day |
| Drills | day-1 drills | human | positive proof lines in the report |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)

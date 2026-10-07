# BUG-172 — Futures Testnet's chart shows mainnet prices while its orders fill on the testnet ("Price shown ≠ fill price")

- **Reported:** 2026-10-07 (the owner, a screenshot of Trade mode on `master-warrior` at `6aa3586`; the coordinator agreed it is a bug and asked for it to be fixed)
- **Severity:** 🔴 P1 — the price a person looks at is not the price their order fills at, for two of the four venues at all times; with `exchange.market_data_venue = futures_testnet` the mismatch turns over and the two mainnet venues show testnet prices behind real money
- **Status:** Open
- **Board:** With Futures Testnet selected in Trade mode the chart reads mainnet prices (a banner says so: "Price shown ≠ fill price"), because every desk, bot chart and venue backtest reads one process-wide market-data setting; two of the four venues are always mismatched.
- **Context:** Trade mode and Bots (`Docs/SPEC/SPEC-002_watch_the_live_market.md`, `SPEC-014_run_a_grid_bot.md`) → `src/modules/market_data/` (`composition/`, `application/`, `contracts/`) → `src/modules/trading/ui/desk/`, `src/modules/bots/ui/`
- **Environment:** `master-warrior` at `6aa3586`; default configuration (`exchange.market_data_venue = mainnet_public`); every venue always on since `EPIC-034B`, mainnet venues since PR #420.

## Reproduction
1. Start the app with the default configuration and open Trade mode on Futures Testnet (or Spot Testnet).
2. Look at the banner and the desk's chart: the banner warns "Chart is showing MAINNET prices, orders fill on TESTNET".

Expected: the chart a person looks at shows the market of the venue they trade on. Actual: the chart, its live stream and the venue's backtests read the one setting `exchange.market_data_venue`. Every time; no precondition.

## Symptom
The screenshot of the owner (banner text above). Nothing in a log: the app does exactly what it is wired to do.

## Root cause
Not yet written down: see the fix commit.

## Fix
Pending.

## Regression test
Pending.

## Verification
Not run.

## Suggested next steps
Fix at the mechanism: a market-data source per venue, the candle store keyed by it, the setting kept for the screens with no venue.

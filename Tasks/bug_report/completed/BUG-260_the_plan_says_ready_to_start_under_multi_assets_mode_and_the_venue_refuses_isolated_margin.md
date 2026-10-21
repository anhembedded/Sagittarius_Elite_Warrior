# BUG-260 — The Plan said "Ready to start" under Multi-Assets Mode, then the venue refused isolated margin (-4168)

- **Reported:** 2026-10-21 (the owner, Futures, via the coordinator session)
- **Severity:** 🟡 P2 — a refusal after "Ready to start" halted the bot; the readiness figure also quoted USD of every asset as USDT
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** Readiness never read the account's asset mode, so Multi-Assets Mode passed the Plan and failed at the venue with `-4168`; fixed by a Futures rule that refuses it in words before Start, and by keeping the margin rule silent beside it.
- **Context:** SPEC run a grid bot → `src/modules/bots/` → `application/services/venue/`, `contracts/`
- **Environment:** master-warrior at `68e1227`, Futures. Reproduced at the unit tier; not on a real exchange.

## Reproduction
1. Put the Futures account in Multi-Assets Mode (wallet in USDC).
2. Design a Grid; the Plan reads "Ready to start". Start.

Expected: refused before Start in words. Actual: `-4168: Unable to adjust to isolated-margin mode under the Multi-Assets mode`, the bot halted. The owner also saw "34.47 USDT available" in Multi-Assets mode (USDC in the wallet) and 0 after switching to Single-Asset.

## Root cause
`FuturesFactsReader._facts` (`futures_facts_reader.py:134`, at `68e1227`) carried the margin and the position mode but not the asset mode; `FuturesFacts` had no field for it (its docstring listed "Multi-Assets mode - a new field with a default and one rule" as a future extension) and `FUTURES_RULES` had no rule. The account summary already reads the mode (`futures_account_reader.py` → `GET /fapi/v1/multiAssetsMargin`), and in Multi-Assets mode its `available_balance` is every margin asset in USD, which the margin rule printed as USDT.

## Fix
- `FuturesFacts.asset_mode` (`AssetMode | None`, default `None`: an unread mode speaks for nothing), read from the connection check's `FuturesAccountSummary` by `FuturesFactsReader`.
- `futures_rules.py` → `multi_assets_mode`: an item `RUN_MULTI_ASSETS_MODE` (`VENUE_NOT_READY`) for Start and Resume: "…Turn off Multi-Assets Mode in Binance Futures preferences (the app never changes it)". `margin_short_for_ladder` is silent under Multi-Assets mode; in Single-Asset mode its text names USDT, the asset the summary counts.

## Regression test
`test_futures_rules.py` (refusal for both purposes, margin silent beside it, Single-Asset and unread mode leave the plan alone, Single-Asset text names USDT) and `test_futures_facts_reader.py` (the mode reaches the facts). Red before: `MULTI_ASSETS_MODE` and `asset_mode` did not exist.

## Verification
Commit tier and `tests/unit/modules/bots` green locally. Not run on a real exchange; the `GET /fapi/v1/multiAssetsMargin` read already served the account summary.

## Not fixed here
A symbol margined in another asset (USDC-margined contracts) is not offered by the app: `_QUOTE_ASSET` stays `"USDT"`.

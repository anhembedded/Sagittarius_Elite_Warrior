# EPIC-026P — `TradingVenue.FUTURES_MAINNET` exists: one reviewed enum member, a venue parameter on the session factory, separate credentials, a fourth alignment state

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.3; ADR D3, D4; `EPIC-021`'s ADR §3 ("a
future epic that has to add a new member here"); the user (2026-09-20): *"hãy cho lô trình để có
thể giao dịch thật"*.
**Risk:** 🔴 — this is the change the whole safety design was built to make reviewable; after it
the app can send an order for real money.
**Complexity:** M — small diff, large consequence; the review is the work.
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** updates `SPEC-003` ("This app does not talk to mainnet"), `SPEC-004` §2, `SPEC-005` §2,
`SPEC-006`/`007`/`010` venue preconditions.
**Depends on:** [`EPIC-026O`](EPIC-026O_reconciliation_script_and_soak_report.md) (gate 2),
[`EPIC-026F`](EPIC-026F_live_candidate_report.md) (gate 1), the ADR **Accepted** by the user with
`O3` answered. Merge requires an independent review by a different session
(`ONBOARDING.md` §7; the reviewer loads the full rubric).

---

## 1. Context and problem

`TradingVenue` is `DISABLED` | `FUTURES_TESTNET` (`trading_venue.py:14-15`).
`FuturesSessionFactory` hard-codes `testnet=True` at `futures_session_factory.py:93` and `:113`
and says in its docstring that it is "never parameterized by venue". Credentials resolve under
Testnet-scoped names only (`env_first_credentials_provider.py:23-24`).
`compute_venue_alignment()` says where the fourth state goes (`venue_alignment.py:48-52`).
Every handler that checks the venue does so with `is not TradingVenue.FUTURES_TESTNET`
(`execute_order/handler.py:192`, `cancel_order/handler.py:93`, `enable_trading/handler.py:100`) —
a comparison that must become "is a live venue" in one place, not three edits.

## 2. Acceptance criteria

- [ ] `TradingVenue.FUTURES_MAINNET = "futures_mainnet"`; the docstring is rewritten to point at
      the ADR and at this task, and says which pull request added the member and who reviewed it.
- [ ] `TradingVenue.is_live` (a property: Testnet and mainnet) replaces the three `is not
      FUTURES_TESTNET` checks; a guard test asserts no `FUTURES_TESTNET` literal appears in
      `application/` handlers.
- [ ] `FuturesSessionFactory` takes the `TradingVenue` and resolves `testnet=` from
      `binance_endpoints.py`'s table, which gains the mainnet row; the guard that only the factory
      constructs a `Client` is unchanged and green.
- [ ] Credentials: `BINANCE_FUTURES_MAINNET_API_KEY` / `_SECRET` (env) and a separate key in
      `secrets.local.json`; the provider resolves **by venue**, and a Testnet key is never returned
      for mainnet or vice versa (unit test: both sets present, each venue gets its own; one set
      present, the other venue gets none).
- [ ] `VenueAlignment` gains `ALIGNED_MAINNET` (mainnet data, mainnet orders) and the banner
      renders it in the danger colour with the words "REAL MONEY"; `DATA_TESTNET_ORDERS_MAINNET`
      is impossible by construction (mainnet orders force `MarketDataVenue.MAINNET_PUBLIC` at
      boot, with a named refusal otherwise).
- [ ] `resolve_trading_venue()` still falls back to `DISABLED` on any unknown value; a typo can
      never select mainnet (`binance_endpoints.py:95`'s rule, extended by a test).
- [ ] `tests/testnet/` stays Testnet-only; no test tier ever targets mainnet.
- [ ] The pull request body carries the independent reviewer's rubric comment link before merge.

## 3. Design

Exactly ADR D3 and D4: one member, one parameter, no flag. The `is_live` property is the "one
place" `architecture-rule.md` §6 requires for a fact two or more handlers read. The credential
provider becomes venue-keyed rather than duplicated (a dictionary of names per venue, one resolve
path). The banner colour is a token from the OS theme's danger role (`ui-presentation-rule.md`),
not a new colour.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/support/binance_gateway/contracts/trading_venue.py` | Member; `is_live`; docstring |
| `src/support/binance_gateway/contracts/binance_endpoints.py` | Mainnet row; resolver test |
| `src/support/binance_gateway/contracts/venue_alignment.py` | Fourth state |
| `src/support/binance_gateway/adapters/env_first_credentials_provider.py`, `secrets_file_source.py` | Venue-keyed names |
| `src/modules/trading/adapters/binance/futures_session_factory.py` | Venue parameter |
| `src/modules/trading/application/{orders/execute_order,orders/cancel_order,session/enable_trading}/handler.py` | `is_live` |
| `src/support/ui_kit/environment_banner/environment_banner_content.py` | Danger rendering |
| `src/shell/…` boot | Force mainnet data with mainnet orders, refuse otherwise |
| `tests/unit/architecture/test_no_testnet_literal_in_handlers.py` | New guard |
| `tests/unit/support/binance_gateway/…` | Provider by venue; resolver typo; alignment |
| `Docs/SPEC/SPEC-003_….md`, `004`, `005`, `006`, `007`, `010` | Venue preconditions |
| `Docs/VOCABULARY/README.md` | `TradingVenue` row updated |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Guards | `pytest tests/unit/architecture -q` | unit (guard) | green, including the new literal guard and the unchanged `LIVE` two-file guard |
| Provider | unit | unit | never cross-venue |
| Resolver | unit | unit | typo → `DISABLED` |
| Alignment | unit | unit | four states, mainnet forces mainnet data |
| Full gate | GitHub Actions `ci-local.ps1 -Full`, log grepped | full | clean |
| Review | independent session, rubric disclosure table | human | linked in the PR |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)

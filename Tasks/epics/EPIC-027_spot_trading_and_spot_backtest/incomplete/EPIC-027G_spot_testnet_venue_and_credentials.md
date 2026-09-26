# EPIC-027G — Spot Testnet exists as a trading venue, with its own keys and honest alignment states

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-26: *"tui muốn giao dịch spot"* ("I want to trade spot").
**Risk:** 🟡 — the venue enum gates order submission; a wrong gate could route a Spot order to Futures, or the reverse.
**Complexity:** M — enum member, credentials, alignment states, Settings, gate checks.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027F](EPIC-027F_venue_selected_trading_client_factory.md). ADR D8 accepted.

---

## 1. Context and problem
- `TradingVenue` has exactly `DISABLED` and `FUTURES_TESTNET`
  (`src/support/binance_gateway/contracts/trading_venue.py:14-15`).
- Three gates compare `is not TradingVenue.FUTURES_TESTNET` literally:
  `execute_order/handler.py:192`, `cancel_order/handler.py:93`, `enable_trading/handler.py:100`.
  A new member would be refused everywhere.
- Credentials are venue-scoped: `BINANCE_FUTURES_TESTNET_API_KEY/_SECRET`
  (`env_first_credentials_provider.py:23-24`). Spot Testnet keys are a separate key set issued at
  `testnet.binance.vision`.
- `compute_venue_alignment` knows testnet versus mainnet only (`venue_alignment.py:74-89`). A Futures
  chart with Spot orders would be reported as aligned.
- The account reader hard-codes `venue=TradingVenue.FUTURES_TESTNET` (`futures_account_reader.py:194`).

## 2. Acceptance criteria
- [ ] `TradingVenue.SPOT_TESTNET` exists with a `market_type` of `SPOT`. `FUTURES_TESTNET` reports
      `FUTURES_USD_M`.
- [ ] Spot Testnet keys are read from `BINANCE_SPOT_TESTNET_API_KEY/_SECRET` only. A Futures key can
      never be read as a Spot key, and a test proves it.
- [ ] The three gates ask "is this a supported trading venue", not "is this Futures Testnet".
      `DISABLED` is still refused everywhere.
- [ ] Venue alignment reports a market mismatch (chart market ≠ trading market) as its own state. The
      environment banner shows it.
- [ ] Settings offers Spot Testnet with a label that says what it is. The restart requirement is
      unchanged (`BOT-125`).

## 3. Design
- A closed enum member, not a flag (`EPIC-021` ADR §3; ADR D8 here). Mainnet Spot is **not** added.
  It enters later as its own reviewed member through `EPIC-026`'s gates (ADR O5).
- `market_type` is a property of the venue, so every downstream consumer (factory, metadata,
  strategy gate, UI) derives the market from one place.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/binance_gateway/contracts/trading_venue.py` | `SPOT_TESTNET`, `market_type` property |
| `src/support/binance_gateway/.../env_first_credentials_provider.py` | Spot Testnet key names |
| `.../venue_alignment.py`, environment banner | market-mismatch state |
| the three handlers above | capability check instead of equality |
| `src/modules/trading/ui/settings/trading_settings_view.py` | the new option and its label |

## 5. Testing
- Unit: enum → market; credential isolation; gates for every member; alignment matrix.
- Sanity: boot with each venue value.
- Not run yet.

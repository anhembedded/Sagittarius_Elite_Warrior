# BOT-170 — The Data Source option is gone: a screen with no venue always reads the public mainnet

**Status:** ✅ Done (2026-10-07)
**Board:** Tools → Options → Market Data no longer offers a Data Source and `exchange.market_data_venue` is deleted, with its resolver. Data mode, the Market mode, historical backtests and the CLI always read the public mainnet; a `user_config.json` that still holds the key is ignored and logged once, and the key still labels the candles stored before BUG-172 (`retired_data_source_setting.py`).
**Source:** the owner, 2026-10-07, approved as one pull request with `BUG-181` and `BOT-171`: remove "Data Source (no trading venue)"; since `BUG-172` every venue screen charts its own venue's market, and a testnet's short history and fake liquidity are no basis for research.
**Risk:** 🟢 — the option only decided screens that act on no venue; the one thing that read the old value at upgrade time, the legacy-candle labelling, is kept
**Complexity:** S — one key, its resolver, one settings control and the guard that listed its readers
**SPEC:** [SPEC-002](../../Docs/SPEC/SPEC-002_watch_the_live_market.md)
**Depends on:** None (`BUG-172` made the option matter to venue-less screens only)

---

## 1. Context and problem
- The Market Data page of Tools → Options offered "Data Source (no trading venue)", backed by `exchange.market_data_venue`, applied only after a restart and read by Data mode, the Market mode, historical backtests and the CLI. Every venue screen already charts its own venue's market (`BUG-172`).
- A testnet as the research source is a trap: short history, fake liquidity. The choice has no user worth keeping.

## 2. Acceptance criteria
- [x] The Market Data page has no Data Source control and Apply writes no `exchange.market_data_venue`.
- [x] The config key, `ConfigKeys.EXCHANGE_MARKET_DATA_VENUE` and `resolve_market_data_venue` are deleted; a screen with no venue reads `DEFAULT_MARKET_DATA_VENUE` (the public mainnet).
- [x] The `BUG-172` guard forbids any reader of the name; the retired key is spelled in code in one file.
- [x] A `user_config.json` that still holds the key does not crash boot: it is ignored and logged once at INFO.
- [x] The one-off legacy-candle labelling still reads the old value (a testnet value still labels the legacy shards as that venue's; an absent key still means the mainnet).
- [x] The SPEC, HLD and vocabulary text that named the option is updated.

## 3. Design
The default venue is a constant, not a setting (`DEFAULT_MARKET_DATA_VENUE`), so there is nothing to resolve and nothing to restart for. The legacy labelling is the one thing that needs the old value, once per data directory (`legacy_store_label.MARKER`): `retired_data_source_setting` reads it, logs that it is ignored, and hands the raw value to `label_legacy_store`, whose rules (a named venue, an absent key, a value that names none → quarantine) are unchanged. That file is the only one allowed to spell the key; the guard now fails on any other, and on any use of the deleted names.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/config/config_keys.py`, `src/config/app_config.json` | The key and its default are removed. |
| `src/support/binance_gateway/contracts/market_data_venue.py` | `DEFAULT_MARKET_DATA_VENUE`. |
| `src/support/binance_gateway/contracts/binance_endpoints.py` | `resolve_market_data_venue` is deleted. |
| `src/modules/market_data/composition/adapter_bindings.py` | The default venue binding is the constant; the legacy labelling gets the retired value. |
| `src/modules/market_data/adapters/persistence/retired_data_source_setting.py` | New: reads the retired key for the labelling and logs once. |
| `src/modules/market_data/ui/settings/*` | The Data Source control, its view-model field, signal and write are removed. |
| `Docs/SPEC/SPEC-002…`, `Docs/HLD/03…`, `Docs/VOCABULARY/README.md` | The option is no longer described. |

## 5. Testing
- `tests/unit/architecture/test_a_venue_screen_charts_its_own_venues_market.py` — no declaration, resolver or reader of the setting; the key is spelled by `retired_data_source_setting.py` only (unit, guard).
- `tests/unit/modules/market_data/adapters/persistence/test_retired_data_source_setting.py` — a leftover key is returned and logged once; an absent key is silent; a value that names no venue does not crash.
- `tests/integration/modules/market_data/adapters/test_legacy_candles_keep_their_source.py` and `…/test_each_venue_charts_from_its_own_market.py` — the labelling still follows the old value through the composed app; a leftover key changes nothing for a venue.
- `tests/unit/modules/market_data/ui/settings/test_market_data_settings_venue.py` — no control, nothing written, a leftover key untouched.

## Implementation notes (written when done)
- `app_config.json` carried `"exchange.market_data_venue": "mainnet_public"` for every install, so a default install's legacy candles were labelled mainnet by that default. With the key gone the labelling sees an absent key, which it already read as the mainnet: the same label, no behaviour change.
- Delivered in the pull request that also carries `BUG-181` and `BOT-171`; not merged.

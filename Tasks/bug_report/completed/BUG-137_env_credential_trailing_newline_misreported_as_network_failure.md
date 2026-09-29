# BUG-137 — Spot/Futures Testnet key with a trailing newline reports a generic "network" failure instead of naming the bad credential

- **Reported:** 2026-09-29 (chat, while the user ran EPIC-027P's AC5 — the real Spot Testnet round trip)
- **Severity:** 🟡 P2 — misdiagnosed a credential formatting mistake as an exchange/connectivity problem, costing a full troubleshooting round before the real cause surfaced
- **Status:** ✅ Fixed (2026-09-29)
- **Context:** `tests/testnet/spot/test_spot_order_lifecycle.py` (EPIC-027P AC5) → `support/binance_gateway` module → `adapters/env_first_credentials_provider.py`
- **Environment:** Windows, user's own checkout, `BINANCE_SPOT_TESTNET_API_KEY`/`_SECRET` set via PowerShell `$env:` assignment

## Reproduction
1. Set `BINANCE_SPOT_TESTNET_API_KEY`/`_SECRET` in PowerShell, with a trailing newline accidentally included in the pasted value (e.g. `$env:X="…\n"` from a paste that carried an extra Enter).
2. Run `pytest tests/testnet/spot/test_spot_order_lifecycle.py::test_market_buy_then_sell_returns_the_holding_to_baseline` with `SEW_TESTNET_TESTS=1`.
3. Expected: either the test passes, or it fails naming a credentials problem. Actual: `baseline_status.reachable` is `False` with `failure=ConnectionFailureKind.NETWORK` — a generic message that gives no hint the key itself was malformed.

## Symptom
```
spot_testnet_credentials = ExchangeCredentials(api_key='----…---\n', api_secret='***')
...
E       AssertionError: network
E       assert False
E        +  where False = ExchangeConnectionStatus(venue=<TradingVenue.SPOT_TESTNET: 'spot_testnet'>, reachable=False, failure=<ConnectionFailureKind.NETWORK: 'network'>, ...).reachable
```
The `repr()` of the resolved credentials shows the literal `\n` at the end of `api_key`.

## Root cause
`EnvFirstCredentialsProvider.resolve()` (`src/support/binance_gateway/adapters/env_first_credentials_provider.py:60-67`, before the fix) read `os.environ.get(...)` verbatim with no normalization. A trailing newline or space — routine when a value is pasted into a shell or sourced from a `.env` file's line ending — became part of the signed request's `X-MBX-APIKEY` header. `requests` rejects a header value containing a control character, which `spot_account_reader._classify_exception()` (and its Futures counterpart) buckets into the generic `ConnectionFailureKind.NETWORK` alongside genuine connectivity failures, since it isn't a `BinanceAPIException` with a named error code. The user-facing message named "network", not "credentials", sending troubleshooting in the wrong direction.

## Fix
`src/support/binance_gateway/adapters/env_first_credentials_provider.py`: added `_stripped_env(name)`, used for both the API key and secret lookups in `resolve()`. Both env var reads now `.strip()` the value before use; a whitespace-only value strips to `""`, which the existing `if api_key and api_secret` falsy check already treats as "not set", falling through to the file source exactly as a genuinely-missing var would (no behavior change for that path). Bounded to the one mechanism that produced the symptom (env var ingestion); `secrets.local.json`-sourced values are untouched since they are written by the app itself, not pasted by a human.

## Regression test
`tests/unit/support/binance_gateway/adapters/test_env_first_credentials_provider.py::test_an_env_var_with_a_trailing_newline_is_stripped_before_use` and `::test_an_env_var_that_is_only_whitespace_falls_back_to_the_file` — both failed before the fix (`'env-key\n' == 'env-key'` and source resolved to `ENV` instead of falling back to `FILE`), pass after. The suite reaches the exact mechanism (`EnvFirstCredentialsProvider.resolve()`), no double stands in for it.

## Verification
```
PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/support/binance_gateway/adapters/test_env_first_credentials_provider.py -q
# 11 passed
.venv/bin/ruff check src/support/binance_gateway/adapters/env_first_credentials_provider.py tests/unit/support/binance_gateway/adapters/test_env_first_credentials_provider.py
.venv/bin/ruff format --check <same two files>
# All checks passed! / already formatted
```
Fast-tier `mypy`/architecture-guard run follows in the same commit's verification pass per `ci-rule.md` §1.

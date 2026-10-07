# BUG-175 — Binance -2008 "Invalid Api-Key ID" is reported as NETWORK: "Nothing stored: NETWORK the key's permissions"

- **Reported:** 2026-10-07 (the owner's `scripts/save_mainnet_key.py spot` on Windows, via the coordinator session)
- **Severity:** 🟢 P3 — a wrong key is refused, but the message blames the network and gives no hint of the real cause.
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** `-2008` (unknown key) and `-2014` (bad key format) were missing from the connection classifier and fell into NETWORK. Fixed: both map to KEY_REJECTED in `connection_failure.py`, and the key sentences and the script say a testnet key does not work on mainnet.
- **Context:** Mainnet key enrolment / Connect step / Options check → `src/modules/trading/adapters/binance/` (`connection_failure.py`, `mainnet/api_restrictions_key_gate.py`), `scripts/save_mainnet_key.py`
- **Environment:** Windows, Spot Mainnet, master `6aa3586`.

## Reproduction
Run `scripts/save_mainnet_key.py spot` with a key the mainnet exchange does not know (most likely a testnet key).

## Symptom
```
Spot Mainnet connection check failed with an unclassified exception: BinanceAPIException: APIError(code=-2008): Invalid Api-Key ID.
Nothing stored: NETWORK the key's permissions
```

## Root cause
`_ERROR_CODE_TO_FAILURE_KIND` in `connection_failure.py` named only -1021, -1022 and -2015; any other code degraded to NETWORK. The gate, the account readers, the Connect step and the Options check all classify through it.

## Fix
`-2008` and `-2014` map to `KEY_REJECTED` in the shared table. `connect_failure_words.py` and `connection_words.py` no longer say the app is testnet-only; both say a testnet key does not work on mainnet, nor the reverse. The script adds a plain line for KEY_REJECTED; exit status stays 1 and nothing is stored. The CLI status formatter's testnet-specific texts are unchanged.

## Regression test
`tests/unit/modules/trading/adapters/binance/test_unknown_key_is_a_rejected_key.py` and the new -2008/-2014 rows of `mainnet/test_api_restrictions_key_gate.py::test_the_exchange_rejecting_the_key_is_named`: red on master with `NETWORK` and the owner's "unclassified exception" log line; green after.

## Verification
Touched suites and commit tier: see the PR. Not run against a live exchange.

# BUG-167 — A real (mainnet) API key shows as KEY_EXPIRED in Tools → Options → Trading

- **Reported:** 2026-10-07 (the owner, in chat: a real Binance key was entered and Options showed "KEY_EXPIRED"; the key was not expired)
- **Severity:** 🟡 P2 — wrong diagnosis; the owner is told to replace a key that is fine
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** Binance `-2015` ("Invalid API-key, IP, or permissions for action") was mapped to `KEY_EXPIRED` in two copies of one table, though no Binance code means expiry; a mainnet key sent to the testnet gets `-2015`. Fixed once: `adapters/binance/connection_failure.py` is the one code→kind table, `-2015` → `KEY_REJECTED`, and the words list the causes (mainnet key on a testnet-only app, IP allowlist, permissions). Held by `test_key_rejected_is_not_key_expired.py`.
- **Context:** Tools → Options → Trading, Check connection → `modules/trading/adapters/binance/`, `ui/market/connection_words.py`, `presentation/cli/exchange_status_formatter.py`
- **Environment:** the owner's desktop; reproduced here by the unit tests (Binance egress is blocked in this sandbox)

## Reproduction
1. Save a mainnet Binance API key in Tools → Options → Trading.
2. Check connection. The Futures/Spot testnet answers `-2015` (it does not know the key).

**Expected:** a message that the key was rejected and why it may be (this app is testnet-only).
**Actual:** `KEY_EXPIRED` / "it may have expired".

## Root cause
- `src/modules/trading/adapters/binance/futures_account_reader.py:80` and `spot/spot_account_reader.py:66` each held a copy of `{-2015: KEY_EXPIRED}`. `-2015` is a catch-all rejection (unknown key, IP off the allowlist, missing permission); "expired" is a guess no code supports. The enum comment (`exchange_connection_status.py:48`) even said "not 'expired' in the literal sense", and the words (`connection_words.py:34`, `exchange_status_formatter.py`) still said it.
- Family scan: the only other Binance-code→failure-kind table is `binance_error_translator.py` (orders, not connection checks) and has no `-2015`. No `ConnectionFailureKind` value is persisted or logged by value (only `.name` in the CLI text), so renaming is safe.

## Fix
- `ConnectionFailureKind.KEY_EXPIRED` removed; `KEY_REJECTED` added (no Binance code means expiry).
- New `adapters/binance/connection_failure.py`: the one code→kind table and `classify_connection_failure`, used by both readers; it logs `App.TradingAdapter` INFO `… rejected: Binance code -2015 -> KEY_REJECTED [connection-failure]`.
- Words (status bar, Options, CLI; Futures and Spot) name the causes and say the app talks to the testnet, so a mainnet key is not accepted. SPEC-003 §5 updated.

## Regression test
`tests/unit/modules/trading/adapters/binance/test_key_rejected_is_not_key_expired.py` — `-2015` from the real Futures and Spot readers yields `KEY_REJECTED` and logs it; no failure kind is named "EXPIRED"; the words (both venues, both renderers) never say "expire" and name testnet, mainnet, allowlist and permission. Red before the fix (5 failed: no `KEY_REJECTED`); green after.

## Verification
- 3990 passed in `tests/unit/modules/trading`, `tests/unit/presentation`, `tests/unit/architecture`, `tests/unit/test_*.py`; `ruff check`/`format` clean; `check_skill_prompt_references.py` OK; mypy shows no error in the touched files.
- Positive proof: the test's `caplog` captures the reader's `Binance code -2015 -> KEY_REJECTED` line.
- Not a case study: no existing net covered the wording.

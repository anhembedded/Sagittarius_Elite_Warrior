# EPIC-034E — A mainnet key is read, never traded: balances, fees and key permissions; withdrawal keys refused

**Status:** ✅ Done (2026-10-07; the owner's manual check with their own key is theirs and is not run)
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🔴 — the first code that talks to the real exchange with the owner's key
**Complexity:** M — a separate account source, a permission check, a guard
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-003](../../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md), extended by this task
**Depends on:** [EPIC-034D](../completed/EPIC-034D_connect_step.md)

---

## 1. Context and problem
The owner's milestone (decision D4): a mainnet key shows the owner's real account. `EPIC-026` D3 keeps the lock on trading, with no mainnet `TradingVenue`; its D6 was cancelled the same day. Today a mainnet key is rejected by the testnet with `-2015` (`BUG-167`).

## 2. Acceptance criteria
- [x] A read-only mainnet `AccountSource` reads balances, commission, open orders and the key's restrictions; it shows as "Mainnet · read only" with the real balances.
- [x] It is not a `TradingVenue`; an architecture guard fails if any import path from it reaches a trading session factory, a trading client or `execute_order`.
- [x] Its credentials resolve from `BINANCE_MAINNET_READONLY_API_KEY` / `_SECRET` only; a testnet key is never read as a mainnet key and the reverse.
- [x] A key whose restrictions allow withdrawals is refused with that reason (D5, once accepted); a key that can trade is accepted with advice to create a read-only key.
- [x] The secret is never written to `secrets.local.json`: the keyring (D10), or the environment.
- [ ] The owner sees their real balances with their own key (manual check): **not run**, see Resume.

## 3. Design
A new type beside the testnet venues, owning only `IVenueAccountReader`. Reuse the Spot and Futures readers' parsing; its session factory has no trading constructor. The permissions come from `GET /sapi/v1/account/apiRestrictions`. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/binance_gateway/` | read-only mainnet endpoints and credentials |
| `src/modules/trading/adapters/binance/` | the read-only source |
| `tests/unit/architecture/` | the no-order-path guard |
| `Docs/SPEC/SPEC-003*` | the mainnet read case |

## 5. Testing
Unit with the fake server: balances parsed, a withdrawal key refused, red first. The guard with a probe. Manual: the owner's key. A reviewer is required; ask the owner before any dependency change (D10). Not run.

## Implementation notes (written when done)
**Delivered** on branch `claude/epic-034-pr3-connect-mainnet-readonly` (PR-3, with `EPIC-034D`, whose `IVenueAccountReader` port and `VenueAccountSnapshot` this uses).

| Criterion | Evidence |
| :--- | :--- |
| Read-only source reads balances, commission, open orders, key restrictions; shows as "Mainnet · read only" | `MainnetReadOnlyAccountReader` (`trading/adapters/binance/mainnet/`), `AccountSource.SPOT_MAINNET_READONLY` (title "Mainnet · read only"); Bots → Mainnet account (`mainnet_account_dialog.py`); `tests/integration/modules/trading/test_mainnet_read_only_account.py::test_a_read_only_key_shows_the_account_with_its_balances_fees_and_orders` and the composed-app test in `test_spot_testnet_boot_on_the_fake_exchange.py` (fake Binance server, python-binance over HTTP) |
| Not a `TradingVenue`; no path to an order | `tests/unit/architecture/test_mainnet_has_no_order_path.py`: walks every runtime import of the source transitively and fails on any trading session factory, trading client, order-submission port or `execute_order`; it found a real path while being written (the source imported a constant from the testnet reader's module, which reaches `i_trading_client_factory`), fixed by moving `QUOTE_ASSET` to the snapshot contract. A probe proves the walk finds direct, transitive and `TYPE_CHECKING`-ignored cases; breaking the source by importing `ITradingClient` turns it red (mutation-checked). The read client port lists exactly seven reads |
| Credentials `BINANCE_MAINNET_READONLY_API_KEY` / `_SECRET` only | `MainnetReadOnlyCredentials`; `test_mainnet_readonly_credentials.py` (no testnet pair is ever read as this one, nor the reverse; half a pair is no key; no file source) |
| A withdrawal key is refused (D5); a trading key accepted with advice | refused with `ConnectionFailureKind.WITHDRAWAL_ENABLED` *before any account data is read* (`..._refused_before_anything_else_is_read` asserts `/api/v3/account` was never requested; mutation-checked); the window shows the advice for a key that can trade |

**Decisions.**
- **Spot only.** The owner's key is a Spot key; a Futures mainnet source is one more `AccountSource` member and reader behind the same port.
- **No push button, a command.** Bots → Mainnet account opens a read-only window that reads on open; it has a Close button and nothing that changes anything.
- **A missing permission flag is a failure, never `False`.** `parse_key_permissions` raises on a missing or non-boolean flag, so an exchange answer without `enableWithdrawals` refuses the key rather than passing it.
- **A key is saved only after it was read.** `scripts/save_mainnet_readonly_key.py` asks for the key and secret (not echoed), reads the account with them (`enrol_key`) and stores them in the keyring only if the read succeeded, so a withdrawal key is never kept (`test_mainnet_key_enrolment.py`). With no usable keyring the save refuses (exit 2) and the environment variables remain the way.
- **`ICredentialsResolver`** is `resolve()` alone: the mainnet source implements the narrow port, so the file-writing method of `IExchangeCredentialsProvider` is not there to call.

## Resume
- **The owner's manual check (the one open criterion).** Set `BINANCE_MAINNET_READONLY_API_KEY` and `BINANCE_MAINNET_READONLY_API_SECRET` to a read-only mainnet key, or run `scripts/save_mainnet_readonly_key.py` once to keep it in the keyring; open the app, Bots → Mainnet account: the real balances show under "Mainnet · read only". A key that can withdraw must show the refusal. The sandbox cannot reach `*.binance.com` (HTTP 451), so this was proven on the fake Binance server only.
- **The keyring (D10)** was first blocked by the session's auto-mode classifier; the owner then allowed adding the package in this session (2026-10-07). `requirements.txt` gains `keyring`; `requirements.lock` was regenerated with the command in `install-rule.md` §2 and its diff is additions only (`keyring 25.7.0` and its own dependencies: `jaraco.*`, `more-itertools`, `jeepney`, `secretstorage`, `cryptography`, `cffi`, `pycparser`, `pywin32-ctypes`); no existing pin moved.
- Verification: commit tier `logs/ci-local-20261007-073401.log` PASS; `tests/unit`, `tests/integration` and `tests/sanity` run by hand, 9,076 passed; the one failure that remains, `test_workbench_conformance[True-1024x700]` (backtest mode needs 719x706), is identical on `master-warrior` in this container. The full gate is GitHub Actions'.

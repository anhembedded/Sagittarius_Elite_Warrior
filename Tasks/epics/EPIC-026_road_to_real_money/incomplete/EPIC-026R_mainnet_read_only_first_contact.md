# EPIC-026R — Mainnet read-only first contact: `exchange-status` with a key that cannot trade or withdraw, and the app checks that it cannot

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §2 success criterion 4; `EPIC-021D`'s
pattern ("the first touch of the real exchange is a read"); the user (2026-09-20): *"hãy cho lô
trình để có thể giao dịch thật"*.
**Risk:** 🟡 — a read; the risk is a key with more permission than intended reaching the app
without the app noticing.
**Complexity:** S — one new check on the account reader, one CLI output line, one human run.
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** updates `SPEC-003` (the check runs on mainnet; permissions are part of "usable").
**Depends on:** [`EPIC-026P`](EPIC-026P_mainnet_venue_member_and_factory_parameter.md)

---

## 1. Context and problem

`EPIC-021D` made the first Testnet contact a read (`main.py exchange-status`: balance, position
mode, clock offset), and that order — read, dry run, one order — is the epic's whole safety
argument. Mainnet gets the same first step, with one thing Testnet never needed: the key's
**permissions**. Binance keys carry `enableReading`, `enableFutures`, `enableWithdrawals` and an
IP restriction; the app today never asks (`futures_account_reader.py` reads balance and position
mode only). The first mainnet key must be reading-only, and the app must refuse to *enable*
trading later with a key that can withdraw.

## 2. Acceptance criteria

- [ ] `ExchangeConnectionStatus` gains `key_permissions` (reading, futures, withdrawals, IP
      restricted) read from the account's API-key permission endpoint through the ACL; a venue
      that does not expose it (Testnet) reports "not available", never "none".
- [ ] `exchange-status` prints the permissions and the IP restriction; on mainnet it prints
      "REAL MONEY" in the header.
- [ ] `EnableTradingCommand` on mainnet refuses with `KEY_CAN_WITHDRAW` if the key has withdrawal
      permission, and with `KEY_NOT_IP_RESTRICTED` unless the user has set
      `trading.mainnet.allow_unrestricted_ip` (a user decision, default off).
- [ ] The human run: the user creates a **reading-only, IP-restricted** mainnet key, runs
      `exchange-status`, and pastes the output (balance masked to two digits) into this file.
      That output is gate 3's evidence for the read half.

## 3. Design

The permission read is one more field on the existing read-only path (`ITradingAccountReader`),
so it is covered by `SPEC-003`'s flow and its fake-server test without a new use case. The
refusal is a safety gate in `EnableTradingCommandHandler` beside the venue and connection
gates — the fourth of what `SPEC-005` calls the three, and the SPEC's §5 table grows by one row.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/exchange_connection_status.py` | `key_permissions` |
| `src/modules/trading/adapters/binance/futures_account_reader.py` | Permission read through the ACL |
| `src/modules/trading/application/session/enable_trading/handler.py` | Two refusals on mainnet |
| `src/modules/trading/contracts/enable_trading_result.py` | Two reasons |
| `src/presentation/cli/exchange_status_formatter.py` | Permissions, "REAL MONEY" header |
| `tests/sanity/binance_fake_server.py` | Permission endpoint with configurable answers |
| `tests/unit/modules/trading/application/session/test_enable_trading.py` | Withdrawal → refuse; unrestricted IP → refuse unless allowed |
| `tests/unit/presentation/cli/test_exchange_status_formatter.py` | Output |
| `Docs/SPEC/SPEC-003_….md`, `SPEC-004_….md` | Rows |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Refusals | unit | unit | both named; Testnet never refuses on "not available" |
| Output | unit | unit | permissions and header |
| Fake server | integration | integration | green |
| Human | `exchange-status` on mainnet with the reading-only key | human | pasted here, masked |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)

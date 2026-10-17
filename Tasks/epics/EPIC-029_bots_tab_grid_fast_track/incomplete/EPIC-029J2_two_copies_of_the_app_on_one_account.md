# EPIC-029J2 — A bot started where another copy of the app already trades the account and symbol is refused or warned

**Status:** 🔵 Backlog — not wanted now (owner, 2026-10-17: *"J2 chưa cần nghĩ tới"*); kept so the gap stays written down
**Source:** the owner's question of 2026-10-16 (why a second bot on the same symbol is refused while a bot on another venue runs), split from `EPIC-029J` on 2026-10-17.
**Risk:** 🔴 — two copies trading one account net their positions and share its balance without either knowing.
**Complexity:** M — an exchange-side or account-scoped mechanism, tested with two data roots on one fake account.
**Epic:** [EPIC-029](../README.md)
**Depends on:** [`EPIC-029J1a`](../completed/EPIC-029J1a_one_active_bot_per_venue.md).

---

## 1. Context and problem
Both checks Start runs, the venue's cap (`other_active_bot`) and the symbol's lease, see only the bots of one data root. Two copies of the app (the desktop and the headless host, each with its own data root) can therefore run a bot on the same account and the same symbol, and neither refuses: their orders, the Futures one-way position (netted per symbol for the whole account) and the account balance would be shared without either knowing. Today the copies trade different accounts (the host Spot mainnet, the desktop Futures Testnet), so nothing collides; the gap opens the day both hold the same account.

## 2. Acceptance criteria
- [ ] A bot started on an account and symbol a bot of **another copy of the app** already trades is refused or warned, naming that holder; the mechanism (for example an exchange-side marker such as the client order id tag prefix, or an account-scoped lease) is chosen when the task starts, and a test with two data roots on one fake account proves it.

## 3. Design
Written when the task starts.

## 4. Changes, per file
Written when the task starts.

## 5. Testing
A test with two data roots on one fake account.

## Implementation notes (written when done)

## Resume (optional; while unfinished)

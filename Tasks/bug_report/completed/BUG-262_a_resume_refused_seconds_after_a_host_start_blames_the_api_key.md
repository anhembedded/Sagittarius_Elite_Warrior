# BUG-262 — A Resume sent seconds after a host start is refused with "check your API key/network connection" though the key is fine

- **Reported:** 2026-10-21 (the owner's VPS journal, relayed by coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`)
- **Severity:** 🟢 P3 — no money at risk; the refusal sends the owner hunting for a key problem that does not exist
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** A refused order session said only "check your API key/network connection" for every failed connection check; the check's own failure kind was dropped at `SessionReadiness`, so a pause or a transient network error read as a key problem. The refusal now carries the kind and words it as the Connect step does (`BUG-262`).
- **Context:** Run a grid bot → bots (`src/modules/bots/`) → `application/services/orders/order_session_opening.py`; trading (`src/modules/trading/`) → `application/session/session_readiness.py`, `contracts/session_block_words.py`
- **Environment:** Owner's VPS host, Futures Testnet, 2026-10-21 (+07). Not captured: the connection check's failure kind at that moment.

## Reproduction
Journal of the host, bot `6tszoz`:

```
19:33:09 [boot-recovery] ... (host just restarted)
19:33:53 [control] resume on 6tszoz -> refused (Connection to the exchange is not ready — check your API key/network connection.)
19:34:08 [control] resume on 6tszoz -> executed
```
The same command passed 15 s later, so the key and the network were fine. Not reproduced against a real exchange; the failing kind is not in the journal.

## Symptom
The refusal names the key. Whatever the connection check found, the text was the same.

## Root cause
`SessionReadiness._ensure_ready_serialised` (`session_readiness.py`, read at `4cb6d47a3`) refuses with `SessionBlockReason.CONNECTION_NOT_READY` when `check_connection()` is not reachable or carries a failure. `SessionReadyResult` had no field for the check's `ConnectionFailureKind`, so the kind (network, an exchange pause, maintenance, a rejected key) was dropped there, and `SESSION_BLOCK_WORDS[CONNECTION_NOT_READY]` had one sentence for all of them. A host that has only just started is the case where the check meets a transient kind (the other candidates: a pause the boot's own reads caused, a first request timing out), and the sentence blamed the key.

## Fix
`SessionReadyResult.connection_failure` carries the check's kind (`session_readiness.py` fills it). `refusal_words` words a connection refusal with the kind's own sentence, from one table in `trading/contracts/connection_failure_words.py` that the Connect step (`bots/.../connect_failure_words.py`) now imports instead of keeping its own copy; a network failure adds "If the host has only just started, try again in a few seconds."; a rate limit or ban says the pause the exchange named (`SessionReadyResult.connection_retry_after`, `connection_banned`), never seconds for a ban; maintenance keeps its own "Wait a few minutes". The same words reach Start, Resume and Stop (`order_session_refusal_words`) and Arm strategy (`arm_strategy/handler.py`), all through `refusal_words`. Not done: a Resume that waits for the connection. The refusal is now truthful and the retry is one command; a wait would hide a real outage behind a hung command (the owner's either-or, option two).

## Regression test
`tests/unit/modules/trading/contracts/test_a_refused_connection_names_its_cause.py` (each kind is worded by its own sentence, a pause and a ban say their length, only a network failure says to retry in seconds, a check that named nothing keeps the old sentence) and `tests/unit/modules/trading/application/session/test_ensure_session_ready.py::test_blocked_when_connection_not_reachable` (the kind reaches the result). Red before: the result has no `connection_failure` and the table does not exist.

## Verification
Unit tiers above plus `tests/unit/modules/bots` (5986 passed locally); the full gate is GitHub Actions' on the pull request. Not run: a real host restart. Positive proof the new path runs is the refusal sentence in the tests; the next occurrence in the owner's journal will name the kind.

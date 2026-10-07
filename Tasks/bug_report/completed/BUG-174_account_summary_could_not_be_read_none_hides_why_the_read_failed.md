# BUG-174 — "Account summary could not be read: None": a rejected key's reason is lost and no notice appears

- **Reported:** 2026-10-07 (the owner's dev log, master `6aa3586`, via the coordinator session)
- **Severity:** 🟡 P2 — the summary panel goes stale with no cause, no notice and no Retry.
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** `GetAccountSummaryQueryHandler` answered `None` for a failed check and dropped `ConnectionFailureKind`, so the log said "None" and no notice appeared. Fixed: it raises `AccountSummaryUnavailableError(kind)`; the log, stale mark and notice (with Retry) name the kind.
- **Context:** Desk account summary → `src/modules/trading/` → `application/queries/get_account_summary/`, `application/account_summary_refresh_service.py`, `ui/desk/account_summary/`
- **Environment:** Windows, Spot Testnet with an invalid key (-2015, expected), master `6aa3586`.

## Reproduction
Open the Spot desk with a key the exchange rejects (-2015). The summary panel is marked stale.

## Symptom
`Account summary could not be read: None`; the panel says only "the account could not be read"; no notice, no Retry.

## Root cause
`get_account_summary/handler.py` returned `status.summary`, which is `None` whenever the connection check failed; `status.failure` (here `KEY_REJECTED`) was dropped on the way. `account_summary_presenter.py` took `detail is None` to mean "answered nothing, raised nothing" and returned before any notice. The refresh service had the same blind spot (its stale reason was "The account could not be read."). This is the open BOT-169 note: the read that answers nothing shows the stale mark with no Retry.

## Fix
- New `contracts/account_summary_unavailable_error.py`: `AccountSummaryUnavailableError(failure)`, with a `reason` text naming the kind.
- The handler raises it when the check names a failure; it still answers `None` only when there is neither a summary nor a failure.
- The refresh service's stale event carries the kind (`The account could not be read (key_rejected).`); the presenter logs it, shows it in the stale mark and reports the background notice with Retry. The presenter's `None` log now reads "no answer".

## Regression test
- `tests/unit/modules/trading/application/queries/test_get_account_summary.py::test_an_unreadable_account_raises_with_the_failure_kind`: red on master (DID NOT RAISE), green after.
- `tests/unit/modules/trading/ui/desk/test_account_summary.py::test_a_rejected_key_is_named_in_the_log_the_stale_mark_and_the_notice` and `test_account_summary_refresh_service.py::test_a_rejected_key_marks_the_summary_stale_with_its_kind`.

## Verification
`tests/unit/modules/trading` passes (2098 tests); commit tier and architecture guards: see the PR.

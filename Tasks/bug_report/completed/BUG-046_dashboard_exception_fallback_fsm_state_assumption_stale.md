# BUG-046 — `test_dashboard_integration_exception_fallback` asserts a stale FSM assumption

**Reported:** 2026-08-25, surfaced by removing BOT-038's `--ignore` on
`tests/integration/presentation/ui/` — this test has been failing on every
commit that directory was excluded from CI, invisibly.
**Severity:** 🟡 P2 — no evidence of a production defect; the test's own
assumption about post-construction FSM state does not hold. Blocks nothing by
itself, but it is currently red in a directory now required by default.
**Status:** ✅ **Fixed 2026-08-25**

## Symptom

```
tests/integration/presentation/ui/test_dashboard_integration.py:102: in test_dashboard_integration_exception_fallback
    assert presenter.fsm.current_state == UIMode.LIVE
AssertionError: assert <UIMode.IDLE: 'IDLE'> == <UIMode.LIVE: 'LIVE'>
```

Deterministic — fails standalone, `1 failed` in isolation, no flakiness.
Reproduces identically at `f27649e`, the commit before this session's own
work began, so it predates everything filed in this session.

## What the test itself already documents

The assertion is preceded by this comment (unchanged, written by whoever wrote
the test):

```python
# BOT-034: construction already auto-started Start Live, and this
# fixture's mock_thread_mgr runs submitted tasks synchronously — so by
# the time we get here, that background run already completed (dispatch
# wasn't broken yet) and landed on LIVE. Not this test's concern (it's
# about _on_load_history's exception handling, not FSM state) — just
# documenting why this isn't IDLE anymore.
assert presenter.fsm.current_state == UIMode.LIVE
```

The premise this comment states — that construction auto-starts Start Live and
lands on `LIVE` before this line runs — is currently false. The FSM is `IDLE`.

## Two candidate explanations, not yet distinguished

1. **BOT-034's autostart behavior changed** since this test was written, and
   the assertion is genuinely stale — the fix is to update or remove it, not
   the production code.
2. **A fixture drift** (`mock_app`, `mock_thread_mgr`) no longer runs the
   submitted task synchronously the way the comment assumes, so `LIVE` is
   never reached in this test's timeline specifically — a test-harness defect,
   not an application one.

Not investigated further here — this bug exists to record the finding BOT-038's
removal surfaced, not to root-cause it. Whoever picks this up: start by
checking whether `DashboardPresenter`'s construction-time autostart still
synchronously reaches `LIVE` under `mock_thread_mgr.submit_sync`, per
`.agents/rules/bug-fix-rule.md`.

## Regression test

This test itself, once its assertion matches real behavior, **is** the
regression test — no new one needed.

## Root cause — confirmed, candidate explanation #1

**BOT-062** (`Tasks/completed/BOT-062_dashboard_autostart_disabled_crash.md`)
changed the config default `DEV_BOARD_AUTOSTART_ENABLED` from `True` to
`False` — a deliberate product decision: opening the Dev Board must not
silently start a live connection unless the user opts in. Confirmed directly:

```python
# dashboard_presenter.py:62
_DEFAULT_AUTOSTART_ENABLED: bool = False
```

This fixture's `mock_config.get.side_effect = lambda key, default=None,
cast=None: default` returns whatever default the caller passes for any key it
doesn't special-case — so `is_autostart_enabled` correctly reads `False`,
`self._autostart` is never constructed, and the FSM stays `IDLE`. The mock is
behaving correctly against current production code; the test's own hard-coded
expectation of `LIVE` is what went stale, written in the BOT-034 era before
BOT-062 changed the default.

Candidate #2 (a fixture drift in `mock_thread_mgr`) was **not** the cause —
the synchronous-submit mock still works exactly as documented; nothing ever
attempts to auto-start in the first place.

## Fix

Updated both assertions to expect `IDLE` (the current, correct default) and
rewrote the explanatory comment to cite BOT-062 instead of only BOT-034. No
production code touched — the app's behavior is correct; only the test's
stale expectation changed. Verified red-then-green: reproduces the original
`AssertionError: assert <UIMode.IDLE> == <UIMode.LIVE>` before the fix
(confirmed via `git stash`/direct diff during investigation), passes after.

Full gate re-run clean: 1,801 passed, 4 skipped, 0 failed.

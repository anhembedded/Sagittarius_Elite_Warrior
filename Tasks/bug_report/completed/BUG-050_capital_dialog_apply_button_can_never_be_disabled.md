# BUG-050 — `CapitalDialogWidget`'s Apply button can never be disabled, even on invalid capital

**Reported date:** 2026-08-25
**Severity:** High (a user can submit an invalid capital value; the disable-on-invalid UX never fires — silent since construction, no test ever exercised it)
**Status:** ✅ Fixed 2026-08-25 — root-caused, regression-tested (confirmed red before / green after), fixed
**Found by:** self-review while working through outstanding session work; the widget had zero test coverage before this bug

---

## Symptom

`CapitalDialogWidget` (`src/presentation/ui/screens/backtest/backtest_modals.py`)
is meant to disable its "Áp dụng" (Apply) button while the typed capital
value is invalid — `_sync_validation()` is wired to
`view_model.capitalValidationMessageChanged` for exactly this. In practice
the button was never disabled under any input, valid or not.

Worse than silently wrong: once the real bug was isolated, calling
`dialog._btn_apply.isEnabled()` on a live dialog raised
`AttributeError: 'NoneType' object has no attribute 'isEnabled'` — the
attribute was not merely stale, it was `None` for the entire lifetime of
every `CapitalDialogWidget` instance ever constructed.

## Root cause

`CapitalDialogWidget.__init__` ends with:

```python
view_model.capitalValidationMessageChanged.connect(self._sync_validation)

self._btn_apply: QPushButton | None = None
```

But `Overlay.__init__` (the base class, `sagittarius_engine...widgets/overlay.py`)
calls `self._build_buttons()` — polymorphically dispatched to
`CapitalDialogWidget._build_buttons()` — **before** `CapitalDialogWidget
.__init__`'s own body runs any further past `super().__init__(...)`:

```python
# Overlay.__init__
super().__init__(parent)
...
outer.addLayout(self._build_buttons())   # <- runs CapitalDialogWidget's override NOW

# CapitalDialogWidget._build_buttons()
self._btn_apply = QPushButton("Áp dụng")   # real button, connected, added to layout
...
```

`Overlay._build_buttons()`'s own docstring says this explicitly: *"called
once, from `Overlay.__init__`, before the subclass's own `__init__` body
runs any further, so a subclass wanting to keep a reference to a button it
creates here must capture it in an instance attribute inside its own
override, not rely on this method's return value being kept around
afterward."* `CapitalDialogWidget._build_buttons()` follows that contract
correctly. The bug is that `CapitalDialogWidget.__init__`'s own body,
resuming *after* `super().__init__()` returns (i.e. after `_build_buttons()`
already ran), re-declares `self._btn_apply: QPushButton | None = None` —
overwriting the real button with `None`, permanently. The button stays
visible and clickable (it was already added to the layout inside
`_build_buttons()`), but the `self._btn_apply` reference the rest of the
class reads is dead from that point on.

`_sync_validation()`'s `if self._btn_apply is not None:` guard then evaluates
`False` forever, so `self._btn_apply.setEnabled(not message)` never executes
— the button can never be disabled by validation state, whatever the typed
capital value is.

## Fix

Deleted the stray `self._btn_apply: QPushButton | None = None` line.
`_build_buttons()` already assigns the real button unconditionally on every
construction (it always runs, from `Overlay.__init__`), so no forward
declaration is needed at all — moved the type annotation onto that one real
assignment instead (`self._btn_apply: QPushButton = QPushButton("Áp dụng")`).
Simplified `_sync_validation()`'s now-always-true `is not None` guard away
since the attribute is guaranteed non-`None` for the object's entire
lifetime.

## Regression test

`tests/unit/presentation/ui/screens/test_backtest_popups_overlay.py::test_capital_dialog_apply_button_disables_on_invalid_capital`
— opens the real Capital dialog through the full `BackTestView`/
`BackTestPresenter` wiring (no mocks on the widget under test), asserts the
button starts enabled, clears the capital field to trigger validation, then
asserts it becomes disabled.

Confirmed red before the fix: `AttributeError: 'NoneType' object has no
attribute 'isEnabled'` at the very first assertion (stashing only the fix
commit's source change, keeping the test). Confirmed green after: all 10
tests in the file pass, plus the file's other 9 (pre-existing) tests
unaffected. Full `tests/unit/presentation/ui/screens/` tier: `546 passed`.

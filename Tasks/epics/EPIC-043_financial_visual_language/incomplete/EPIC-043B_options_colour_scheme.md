# EPIC-043B — Option A: the colour scheme is chosen in Tools → Options, and the series colours are contrast-checked in both schemes

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-20, accepting [PRO-009](../../../proposal/PRO-009.md) options A + B (*"OK"*; default System, tick flash off by default)
**Risk:** 🟡 — a UI change that must not reintroduce a style layer; the three guards hold it
**Complexity:** M — see PRO-009 §4
**Epic (optional):** [EPIC-043](../README.md)
**Depends on:** 043A

---

## 1. Context and problem
Tools → Options gets System (default), Light, Dark, applied with `QStyleHints.setColorScheme`; no palette, style sheet or colour is written. The series colours (`series_colours.py`) are checked for contrast in both schemes, with one alternative per scheme where one fails (PRO-009 §2 A). Amends `ui-presentation-rule.md` where it says visual design is deferred.

## 2. Acceptance criteria
- [ ] Options offers System, Light and Dark; System is the default; the choice persists and applies without a restart.
- [ ] No `setStyleSheet`, `QPalette` write or colour literal is added; `test_stock_controls_only.py`, `test_no_global_stylesheet.py` and `test_app_styling_only_shrinks.py` are unchanged or tighter.
- [ ] A test fails when a series colour falls under the contrast threshold in either scheme.
- [ ] Preview frames in both schemes at 1024×700, 1366×768 and 1920×1080; the conformance suite passes at all three sizes in both.

## 3. Design
To be written when the task starts; it applies PRO-009 §2 and `EPIC-033` D1 and D8 as amended 2026-10-20. No style sheet, no app palette, no third-party theme package.

## 3a. Reuse
To be filled when the task starts (`.claude/rules/capabilities.md`): `meaning_colours.py`, `Tone`, `series_colours.py`, the Lucide icon set.

## 4. Changes, per file
To be filled when the task starts.

## 5. Testing
To be filled when the task starts; preview frames at 1024×700, 1366×768 and 1920×1080 in both schemes (code tasks).

## 6. Docs touched
To be filled when the task starts.

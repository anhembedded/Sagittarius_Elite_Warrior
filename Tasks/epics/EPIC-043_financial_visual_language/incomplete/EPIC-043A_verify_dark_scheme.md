# EPIC-043A — Verify: every mode under the dark scheme at 1366×768

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-20, accepting [PRO-009](../../../proposal/PRO-009.md) options A + B (*"OK"*; default System, tick flash off by default)
**Risk:** 🟢 — read-only evidence
**Complexity:** S — see PRO-009 §4
**Epic (optional):** [EPIC-043](../README.md)
**Depends on:** None

---

## 1. Context and problem
Screenshot every mode under the dark colour scheme at 1366×768, offscreen with `QStyleHints.setColorScheme` or the platform, and record what already reads well and what does not (PRO-009 §4 step 1). Nobody has looked yet (PRO-009 §1, Unknown).

## 2. Acceptance criteria
- [ ] A frame of every mode in the dark scheme at 1366×768 exists under the task's evidence folder, with the exact command that produced it.
- [ ] The task records, per mode, what reads well and what fails (unreadable text, a chart that ignores the palette, a hard-coded light surface).
- [ ] Whether `setColorScheme` is available and effective offscreen is recorded as a fact (requirements.lock pins PySide6 6.11.1).

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

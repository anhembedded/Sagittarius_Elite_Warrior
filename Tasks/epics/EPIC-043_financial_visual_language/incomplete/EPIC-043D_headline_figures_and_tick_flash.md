# EPIC-043D — B3 + B4: headline figures, and the tick flash toggle

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-20, accepting [PRO-009](../../../proposal/PRO-009.md) options A + B (*"OK"*; default System, tick flash off by default)
**Risk:** 🟡 — a UI change that must not reintroduce a style layer; the three guards hold it
**Complexity:** M — see PRO-009 §4
**Epic (optional):** [EPIC-043](../README.md)
**Depends on:** 043C

---

## 1. Context and problem
Equity, today's PnL, open position and liquidation distance sit in one row above the detail, in a larger, bolder size derived from the system font and the platform's fixed-pitch font for digits. A price cell briefly takes the up or down tone on a tick, behind an Options toggle that is off by default; the arrow stays as the non-colour signal.

## 2. Acceptance criteria
- [ ] The headline row shows the four figures through the application's formatter, derived from the system font, no family set.
- [ ] The tick flash is an Options toggle, off by default; off, a price cell never changes colour on a tick; on, it takes the tone and returns to the platform colour.
- [ ] No timer or animation outlives its widget (async-ui-action-rule), checked by a test.
- [ ] A before/after preview frame for each touched screen.

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

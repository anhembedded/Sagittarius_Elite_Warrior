# EPIC-043E — B5 + B6: risk tones and Lucide icons

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-20, accepting [PRO-009](../../../proposal/PRO-009.md) options A + B (*"OK"*; default System, tick flash off by default)
**Risk:** 🟡 — a UI change that must not reintroduce a style layer; the three guards hold it
**Complexity:** M — see PRO-009 §4
**Epic (optional):** [EPIC-043](../README.md)
**Depends on:** 043D

---

## 1. Context and problem
The liquidation read-out and the risk watch's SAFE / WARN / CRITICAL use a warning tone with the word beside it; commands and states get SVG icons from the existing Lucide set under `src/support/ui_kit/assets/icons/`.

## 2. Acceptance criteria
- [ ] SAFE, WARN and CRITICAL each carry a word and a tone from the meaning table; the liquidation read-out is toned the same way.
- [ ] Every new icon is an SVG from the Lucide set; no emoji; icon-only actions keep a tooltip naming the shortcut.
- [ ] A before/after preview frame for each touched screen; the epic's success criteria (README §2) are all measured.

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
